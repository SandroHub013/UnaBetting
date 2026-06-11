import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import log_loss, accuracy_score, roc_auc_score
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class TennisNet(nn.Module):
    """
    Deep Neural Network for predicting tennis matches using 150+ features.
    Architecture: Multi-Layer Perceptron (MLP) with Batch Normalization and Dropout 
    to prevent overfitting on the complex historical stats.
    """
    def __init__(self, input_dim):
        super(TennisNet, self).__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.4),
            
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            nn.Linear(64, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x):
        return self.network(x)

def load_and_scale_data():
    from src.models.train import prepare_training_data, load_config
    features_path = PROJECT_ROOT / "data" / "features" / "atp_features.csv"
    if not features_path.exists():
        raise FileNotFoundError(f"Feature matrix not found: {features_path}")
        
    df = pd.read_csv(features_path)
    config = load_config()
    
    X_train_scaled, y_train, _X_val, _y_val, X_test_scaled, y_test, scaler, numeric_cols, _medians = prepare_training_data(df, config)
    
    # Riempi eventuali NaNs rimasti causati da scaling
    X_train_scaled = np.nan_to_num(X_train_scaled.values, nan=0.0, posinf=0.0, neginf=0.0)
    X_test_scaled = np.nan_to_num(X_test_scaled.values, nan=0.0, posinf=0.0, neginf=0.0)
    
    return X_train_scaled, y_train.values, X_test_scaled, y_test.values

def train_dl_model():
    print("🧠 Inizializzando Architettura Deep Learning (PyTorch)...")
    X_train, y_train, X_test, y_test = load_and_scale_data()
    
    input_dim = X_train.shape[1]
    
    # Conversione in tensori
    X_train_tensor = torch.FloatTensor(X_train)
    y_train_tensor = torch.FloatTensor(y_train).view(-1, 1)
    
    X_test_tensor = torch.FloatTensor(X_test)
    y_test_tensor = torch.FloatTensor(y_test).view(-1, 1)
    
    # DataLoader
    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)
    train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)
    
    # Inizializza Modello
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} | Features: {input_dim}")
    
    model = TennisNet(input_dim).to(device)
    criterion = nn.BCELoss()
    optimizer = optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', patience=3, factor=0.5)
    
    epochs = 40
    best_loss = float('inf')
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * batch_X.size(0)
            
        train_loss /= len(train_loader.dataset)
        
        # Validation
        model.eval()
        with torch.no_grad():
            test_outputs = model(X_test_tensor.to(device))
            val_loss = criterion(test_outputs, y_test_tensor.to(device)).item()
            
        scheduler.step(val_loss)
        
        if val_loss < best_loss:
            best_loss = val_loss
            torch.save(model.state_dict(), PROJECT_ROOT / "models" / "best_tennis_dnn.pth")
            
        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"Epoch [{epoch+1}/{epochs}] | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")
            
    print("\n✅ Training DNN Terminata!")
    
    # Load Best Model for Evaluation
    model.load_state_dict(torch.load(PROJECT_ROOT / "models" / "best_tennis_dnn.pth"))
    model.eval()
    with torch.no_grad():
        preds_prob = model(X_test_tensor.to(device)).cpu().numpy()
        preds_class = (preds_prob > 0.5).astype(int)
        
    acc = accuracy_score(y_test, preds_class)
    ll = log_loss(y_test, preds_prob)
    auc = roc_auc_score(y_test, preds_prob)
    
    print(f"\n📊 Deep Learning Performance:")
    print(f"Accuracy: {acc:.4f} | Log Loss: {ll:.4f} | ROC AUC: {auc:.4f}")

if __name__ == "__main__":
    train_dl_model()

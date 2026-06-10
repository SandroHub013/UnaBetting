import torch
import torch.nn as nn
import torch.optim as optim

class TennisEmbeddingNet(nn.Module):
    def __init__(self, num_players, embedding_dim, num_numerical_features, hidden_layers=[128, 64, 32], dropout_rate=0.3):
        """
        Args:
            num_players (int): Total number of unique players in the dataset.
            embedding_dim (int): Dimension of the player embedding vectors.
            num_numerical_features (int): Number of continuous features (ELO, hold_pct, etc.).
            hidden_layers (list): Number of neurons in each hidden layer.
            dropout_rate (float): Dropout probability.
        """
        super(TennisEmbeddingNet, self).__init__()
        
        # Embedding layer for players. Shared for both player 1 and player 2.
        # We use a shared embedding because the player characteristics remain the same regardless of whether they are player 1 or 2.
        self.player_embedding = nn.Embedding(num_embeddings=num_players, embedding_dim=embedding_dim)
        
        # Calculate the total input dimension for the first dense layer
        # 3 * embedding_dim (for player 1, player 2, and their difference) + numerical features
        input_dim = (3 * embedding_dim) + num_numerical_features
        
        # Build the dense layers
        layers = []
        current_dim = input_dim
        
        for hidden_dim in hidden_layers:
            layers.append(nn.Linear(current_dim, hidden_dim))
            layers.append(nn.GELU()) # GELU activation
            layers.append(nn.BatchNorm1d(hidden_dim)) # Batch Normalization for stability
            layers.append(nn.Dropout(dropout_rate)) # Dropout for regularization
            current_dim = hidden_dim
            
        # Final output layer for binary classification (win/loss probability)
        layers.append(nn.Linear(current_dim, 1))
        layers.append(nn.Sigmoid())
        
        self.fc_layers = nn.Sequential(*layers)

    def forward(self, p1_id, p2_id, numerical_features):
        """
        Forward pass.
        Args:
            p1_id (Tensor): Tensor of shape (batch_size,) with player 1 IDs.
            p2_id (Tensor): Tensor of shape (batch_size,) with player 2 IDs.
            numerical_features (Tensor): Tensor of shape (batch_size, num_numerical_features).
        Returns:
            Tensor: Probabilities of player 1 winning.
        """
        # Get embeddings
        p1_emb = self.player_embedding(p1_id) # (batch_size, embedding_dim)
        p2_emb = self.player_embedding(p2_id) # (batch_size, embedding_dim)
        
        # Calculate embedding difference to explicitly model player interaction
        emb_diff = p1_emb - p2_emb
        
        # Concatenate embeddings, their difference, and numerical features
        # Shape: (batch_size, 3*embedding_dim + num_numerical_features)
        x = torch.cat([p1_emb, p2_emb, emb_diff, numerical_features], dim=1)
        
        # Pass through dense layers
        output = self.fc_layers(x)
        return output

class TennisTransformerNet(nn.Module):
    def __init__(self, num_players, embedding_dim, num_numerical_features, num_heads=4, num_layers=2, hidden_layers=[128, 64], dropout_rate=0.3):
        """
        Transformer-based architecture inspired by TCDformer to capture 
        relational dynamics and "momentum" between players and match context.
        """
        super(TennisTransformerNet, self).__init__()
        
        self.player_embedding = nn.Embedding(num_embeddings=num_players, embedding_dim=embedding_dim)
        self.feature_proj = nn.Linear(num_numerical_features, embedding_dim)
        
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=embedding_dim, 
            nhead=num_heads, 
            dim_feedforward=embedding_dim * 4, 
            dropout=dropout_rate,
            activation='gelu',
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.token_type_embeddings = nn.Embedding(4, embedding_dim)
        
        input_dim = embedding_dim * 4
        layers = []
        current_dim = input_dim
        for hidden_dim in hidden_layers:
            layers.append(nn.Linear(current_dim, hidden_dim))
            layers.append(nn.GELU())
            layers.append(nn.BatchNorm1d(hidden_dim))
            layers.append(nn.Dropout(dropout_rate))
            current_dim = hidden_dim
            
        layers.append(nn.Linear(current_dim, 1))
        layers.append(nn.Sigmoid())
        
        self.fc_layers = nn.Sequential(*layers)

    def forward(self, p1_id, p2_id, numerical_features):
        batch_size = p1_id.size(0)
        device = p1_id.device
        
        p1_emb = self.player_embedding(p1_id)
        p2_emb = self.player_embedding(p2_id)
        emb_diff = p1_emb - p2_emb
        feat_emb = self.feature_proj(numerical_features)
        
        tokens = torch.stack([p1_emb, p2_emb, emb_diff, feat_emb], dim=1)
        token_ids = torch.arange(4, device=device).unsqueeze(0).expand(batch_size, 4)
        tokens = tokens + self.token_type_embeddings(token_ids)
        
        transformed = self.transformer(tokens)
        flattened = transformed.reshape(batch_size, -1)
        return self.fc_layers(flattened)


def train_tennis_model(model, train_loader, val_loader, epochs=10, lr=0.001):
    """
    Skeleton training loop for the TennisEmbeddingNet.
    
    Args:
        model (nn.Module): The neural network model.
        train_loader (DataLoader): DataLoader for training data.
        val_loader (DataLoader): DataLoader for validation data.
        epochs (int): Number of training epochs.
        lr (float): Learning rate.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    
    # Binary Cross Entropy Loss for binary classification
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5) # Adam with L2 regularization
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        
        for batch in train_loader:
            # Unpack batch (assuming batch contains p1_ids, p2_ids, num_features, labels)
            p1_ids = batch['p1_id'].to(device)
            p2_ids = batch['p2_id'].to(device)
            num_features = batch['numerical_features'].to(device)
            labels = batch['label'].to(device).float().unsqueeze(1) # Match output shape
            
            # Zero gradients
            optimizer.zero_grad()
            
            # Forward pass
            outputs = model(p1_ids, p2_ids, num_features)
            
            # Compute loss
            loss = criterion(outputs, labels)
            
            # Backward pass and optimize
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * p1_ids.size(0)
            
        train_loss /= len(train_loader.dataset)
        
        # Validation phase
        model.eval()
        val_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch in val_loader:
                p1_ids = batch['p1_id'].to(device)
                p2_ids = batch['p2_id'].to(device)
                num_features = batch['numerical_features'].to(device)
                labels = batch['label'].to(device).float().unsqueeze(1)
                
                outputs = model(p1_ids, p2_ids, num_features)
                loss = criterion(outputs, labels)
                val_loss += loss.item() * p1_ids.size(0)
                
                # Calculate accuracy
                predictions = (outputs >= 0.5).float()
                correct += (predictions == labels).sum().item()
                total += labels.size(0)
                
        val_loss /= len(val_loader.dataset)
        accuracy = correct / total
        
        print(f"Epoch {epoch+1}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {accuracy:.4f}")
        
    return model

if __name__ == "__main__":
    # Quick test to ensure the model instantiates and forwards correctly
    num_players = 5000
    emb_dim = 32
    num_features = 20
    batch_size = 64
    
    model = TennisTransformerNet(num_players, emb_dim, num_features)
    print("Model Architecture:")
    print(model)
    
    # Dummy data
    dummy_p1 = torch.randint(0, num_players, (batch_size,))
    dummy_p2 = torch.randint(0, num_players, (batch_size,))
    dummy_features = torch.randn(batch_size, num_features)
    
    # Dummy forward pass
    out = model(dummy_p1, dummy_p2, dummy_features)
    print(f"\nOutput shape: {out.shape}") # Should be (64, 1)

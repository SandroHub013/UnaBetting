import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

def main():
    print("Generating Ed25519 keypair for updater...")
    priv = ed25519.Ed25519PrivateKey.generate()
    pub = priv.public_key()
    
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    key_dir = Path("keys")
    key_dir.mkdir(exist_ok=True)
    
    (key_dir / "updater_private.pem").write_bytes(priv_pem)
    (key_dir / "updater_public.pem").write_bytes(pub_pem)
    
    print("Private key saved to keys/updater_private.pem")
    print("Public key saved to keys/updater_public.pem")
    
    print("\nPublic Key to embed in src/dashboard/data_api.py:")
    print("--------------------------------------------------")
    print(pub_pem.decode('utf-8'))
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

rsa_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
rsa_public_key = rsa_private_key.public_key()

rsa_private_key_pem = rsa_private_key.private_bytes(encoding = serialization.Encoding.PEM, format = serialization.PrivateFormat.PKCS8, encryption_algorithm = serialization.NoEncryption())
rsa_public_key_pem = rsa_public_key.public_bytes(encoding = serialization.Encoding.PEM, format = serialization.PublicFormat.SubjectPublicKeyInfo)

with open("manager_private_key.pem", "wb") as f:
    f.write(rsa_private_key_pem)

with open("manager_public_key.pem", "wb") as f:
    f.write(rsa_public_key_pem)

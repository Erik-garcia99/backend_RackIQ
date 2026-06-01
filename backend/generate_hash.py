import bcrypt
hashed = b"$2b$12$N/vysK72ISUcw135amfSA.ulpNWuXVV2vVFmRoCci2eBFGgjOlxaK"
try:
    match = bcrypt.checkpw(b"Test123!@#", hashed)
    print("Match raw bcrypt:", match)
except Exception as e:
    print("Error raw bcrypt:", e)

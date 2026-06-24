from passlib.context import CryptContext

from dynamoDB.auth_services import (
    create_user,
    get_user_by_email,
    user_exists
)

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(
        plain_password: str,
        hashed_password: str
):
    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def signup(
        email: str,
        name: str,
        password: str
):
    if user_exists(email):
        return {
            "success": False,
            "message": "Email already exists"
        }

    password_hash = hash_password(password)

    create_user(
        email=email,
        name=name,
        password_hash=password_hash
    )

    return {
        "success": True,
        "message": "User created successfully"
    }


def login(
        email: str,
        password: str
):
    user = get_user_by_email(email)

    if not user:
        return {
            "success": False,
            "message": "Invalid email or password"
        }

    if not verify_password(
            password,
            user["password_hash"]
    ):
        return {
            "success": False,
            "message": "Invalid email or password"
        }

    return {
        "success": True,
        "message": "Login successful",
        "user": {
            "email": user["email"],
            "name": user["name"]
        }
    }
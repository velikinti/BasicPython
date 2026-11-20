from db.orm.user_data_table import UserData
from datetime import datetime
from db_connection import db_session

# Create a new user in the database
def create_user(username: str, password: str):
    try:
        with db_session() as session:
            session.execute("Select * from user_data where user_name = %s", (username,))
            user_info = session.fetchone()
            if user_info:
                raise ValueError("User already exists.")
            new_user = UserData(user_name=username, password=password, created_at=datetime.utcnow(), updated_at=datetime.utcnow())
            session.execute("INSERT INTO user_data (user_name, password, created_at, updated_at) VALUES (%s, %s, %s, %s)",
                            (new_user.user_name, new_user.password, new_user.created_at, new_user.updated_at))
            session.connection.commit()
            return new_user
    except Exception as e:
        print(f"Error creating user: {e}")
        raise e

# Get user by username
def get_user_by_username(username: str):
    try:
        with db_session() as session:
            session.execute("Select * from user_data where user_name = %s", (username,))
            user_info = session.fetchone()
            if not user_info:
                raise ValueError("User not found.")
            return UserData(user_name=user_info['user_name'], password=user_info['password'], created_at=user_info['created_at'], updated_at=user_info['updated_at'])
    except Exception as e:
        print(f"Error fetching user: {e}")
        raise e
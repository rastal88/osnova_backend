from enum import Enum

class Role(str, Enum):
    ADMIN = "admin"
    MODERATOR = "moderator"
    USER = "user"


PERMISSIONS = {
    Role.USER: ["read_own_data"],
    Role.ADMIN: ["read_all_data", "manage_users"],
    Role.MODERATOR: ["read_all_data"],
}
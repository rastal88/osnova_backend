from enum import Enum

class Role(str, Enum):
    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"

# Права доступа для каждой роли
PERMISSIONS = {
    Role.USER: ["read_own_data"],
    Role.ADMIN: ["read_all_data", "manage_users"],
    Role.MODERATOR: ["read_all_data"],
}
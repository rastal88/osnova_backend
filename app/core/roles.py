from enum import Enum

class Role(str, Enum):
    ROOT = "root"
    MODERATOR = "moderator"
    USER = "user"


PERMISSIONS = {
    Role.USER: ["read_own_data"],
    Role.ROOT: ["read_all_data", "manage_users"],
    Role.MODERATOR: ["read_all_data"],
}
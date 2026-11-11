from app.modules.auth.permissions import permission

LEADS_READ = permission("leads.read")
# Change the status, delete
LEADS_MANAGE = permission("leads.manage")
LEADS_EXPORT = permission("leads.export")

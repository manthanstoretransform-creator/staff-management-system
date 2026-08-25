from app.core.database import get_session_local
from app.services.project_management import ProjectManagementService
from app.models.user import User

db = get_session_local()()
user = db.query(User).first()
if user:
    try:
        res = ProjectManagementService.list(db, user, 1, 20, None, None, None, None)
        print("Success:", len(res['items']))
    except Exception as e:
        import traceback
        traceback.print_exc()
else:
    print('No user')
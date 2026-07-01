from app import create_app
from app.infrastructure.persistence.models.user_model import UserModel
from app.infrastructure.persistence.models.device_model import Device
import re

app = create_app()
with app.app_context():
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    masked_uri = re.sub(r':([^@]+)@', ':***@', db_uri)
    print('DB_URI: ' + str(masked_uri))

    user = UserModel.query.filter_by(username='demothesisiot').first()
    if user:
        print('USER:' + str(user.id) + '|' + str(user.username))
        devices = Device.query.filter_by(user_id=user.id).all()
        for d in devices:
            print('DEV:' + str(d.id) + '|' + str(d.name) + '|' + str(d.code) + '|' + str(d.category) + '|' + str(d.control_types) + '|' + str(d.status_value) + '|' + str(d.is_on) + '|' + str(d.room_id))
    else:
        print('USER:NOT_FOUND')
        users = UserModel.query.all()
        print('DEMO_USERS:' + ','.join([u.username for u in users]))

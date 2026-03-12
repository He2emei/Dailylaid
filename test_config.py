import sys
sys.path.insert(0, 'e:/Project/myAIApp/Dailylaid_Dev')
from config import Config

def test():
    data = {
        'post_type': 'message',
        'message_type': 'group',
        'user_id': 12345,
        'group_id': 1087453112,
        'raw_message': '提醒我3分钟后喝水'
    }
    
    group_id = str(data.get('group_id', '')) if data.get('group_id') else None
    user_id = str(data.get('user_id', ''))
    
    print('groups in config:', Config.ALLOWED_GROUPS)
    print('group_id extract:', repr(group_id))
    print('is_allowed:', Config.is_allowed(user_id, group_id))

if __name__ == '__main__':
    test()

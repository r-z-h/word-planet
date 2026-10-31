"""定级测试：不会时可直接跳过（提交空答案）仍能推进。"""


def test_skip_question_advances(user_client):
    c = user_client
    start = c.post('/api/test/start')
    assert start.status_code == 200, start.text
    q = start.json()['question']
    r = c.post('/api/test/answer', json={'question_id': q['id'], 'answer': ''})
    assert r.status_code == 200, r.text
    d = r.json()
    # 要么还有下一题，要么直接结束（10 题都要跳过才会结束）
    assert d['is_finished'] is True or d.get('next_question') is not None

from .competition_collector import start_collection, KINDS


def handle(handler, method, path, query=None, body=None):
    store = handler.server.competitions
    endpoint = path.removeprefix('/api/competition/').strip('/')
    query = query or {}
    one = lambda key, default='':query.get(key,[default])[0]
    if method=='GET':
        limit,offset = int(one('limit','10')),int(one('offset','0'))
        if endpoint=='catalog':
            return handler._send(200,{**store.list_catalog(one('q'),one('group')),'kinds':KINDS})
        if endpoint.startswith('catalog/'):
            item = next((x for x in store.list_catalog()['items'] if x['id']==endpoint.split('/')[1]),None)
            return handler._send(200,item) if item else handler._send(404,{'error':'赛事不存在'})
        if endpoint=='notices':
            return handler._send(200,store.list_notices(q=one('q'),competition=one('competition'),kind=one('kind'),tab=one('tab','all'),limit=limit,offset=offset))
        if endpoint.startswith('notices/'):
            item = store.get_notice(int(endpoint.split('/')[1]))
            return handler._send(200,item) if item else handler._send(404,{'error':'赛事通知不存在'})
        if endpoint=='subscriptions': return handler._send(200,store.subscriptions())
        if endpoint=='messages': return handler._send(200,store.list_messages(limit,offset))
        if endpoint=='crawl': return handler._send(200,store.crawl_state())
        if endpoint=='settings': return handler._send(200,store.settings())
    elif method=='PUT':
        if endpoint=='subscriptions':
            if set(body)!={'competitions'}: raise ValueError('需要 competitions 字段')
            return handler._send(200,store.save_subscriptions(body['competitions']))
        if endpoint=='settings': return handler._send(200,store.save_settings(body))
    elif method=='PATCH':
        if endpoint.startswith('notices/'):
            item = store.update_notice(int(endpoint.split('/')[1]),body)
            return handler._send(200,item) if item else handler._send(404,{'error':'赛事通知不存在'})
        if endpoint=='messages' or endpoint.startswith('messages/'):
            if body!={'read':True}: raise ValueError('消息仅支持标记已读')
            count = store.read_messages(int(endpoint.split('/')[1]) if '/' in endpoint else None)
            return handler._send(200,{'ok':True}) if count or endpoint=='messages' else handler._send(404,{'error':'消息不存在'})
    elif method=='POST':
        if endpoint=='crawl':
            if set(body)-{'competition_id'}: raise ValueError('只支持 competition_id')
            id = body.get('competition_id')
            if id is not None and not isinstance(id,str): raise ValueError('competition_id 必须是字符串')
            if not start_collection(store,id): return handler._send(409,{'error':'赛事采集正在运行'})
            return handler._send(200,{'ok':True,'running':True})
        if endpoint=='crawl/stop':
            if body: raise ValueError('停止采集不接受参数')
            store.stop(); return handler._send(200,{'ok':True,'stopping':True})
    return handler._send(404,{'error':'赛事接口不存在'})

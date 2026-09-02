# Test Execution Report

**Result:** tests failed (exit code 1, 1 test file(s), 17 source file(s))

**Exit code:** 1

**Test files:** 1

**Source files:** 17


## stdout

```
=== Backend (pytest) ===
F.FF.FFFFFF                                                              [100%]
=================================== FAILURES ===================================
___________________________ test_create_run_success ____________________________
tests/test_runs.py:40: in test_create_run_success
    resp = client.post("/runs", json=payload)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
_______________________ test_list_runs_contains_created ________________________
tests/test_runs.py:76: in test_list_runs_contains_created
    created = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
_____________________________ test_get_run_detail ______________________________
tests/test_runs.py:96: in test_get_run_detail
    created = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
____________________________ test_join_run_success _____________________________
tests/test_runs.py:134: in test_join_run_success
    run = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
_______________________ test_join_run_duplicate_rejected _______________________
tests/test_runs.py:153: in test_join_run_duplicate_rejected
    run = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
___________________________ test_join_run_empty_name ___________________________
tests/test_runs.py:176: in test_join_run_empty_name
    run = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
____________________________ test_leave_run_success ____________________________
tests/test_runs.py:194: in test_leave_run_success
    run = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
_____________________ test_leave_run_participant_not_found _____________________
tests/test_runs.py:217: in test_leave_run_participant_not_found
    run = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
__________________________ test_leave_run_empty_name ___________________________
tests/test_runs.py:235: in test_leave_run_empty_name
    run = client.post("/runs", json={
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:546: in post
    return super().post(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1144: in post
    return self.request(
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:445: in request
    return super().request(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:825: in request
    return self.send(request, auth=auth, follow_redirects=follow_redirects)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:914: in send
    response = self._send_handling_auth(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:942: in _send_handling_auth
    response = self._send_handling_redirects(
/usr/local/lib/python3.11/site-packages/httpx/_client.py:979: in _send_handling_redirects
    response = self._send_single_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/httpx/_client.py:1014: in _send_single_request
    response = transport.handle_request(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:348: in handle_request
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/testclient.py:345: in handle_request
    portal.call(self.app, scope, receive, send)
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:334: in call
    return cast(T_Retval, self.start_task_soon(func, *args).result())
                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:456: in result
    return self.__get_result()
           ^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/concurrent/futures/_base.py:401: in __get_result
    raise self._exception
/usr/local/lib/python3.11/site-packages/anyio/from_thread.py:259: in _call_func
    retval = await retval_or_awaitable
             ^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/applications.py:1160: in __call__
    await super().__call__(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/applications.py:107: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:186: in __call__
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py:164: in __call__
    await self.app(scope, receive, _send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/cors.py:87: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/middleware/exceptions.py:63: in __call__
    await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/middleware/asyncexitstack.py:18: in __call__
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:716: in __call__
    await self.middleware_stack(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:736: in app
    await route.handle(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/routing.py:290: in handle
    await self.app(scope, receive, send)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:130: in app
    await wrap_app_handling_exceptions(app, request)(scope, receive, send)
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:53: in wrapped_app
    raise exc
/usr/local/lib/python3.11/site-packages/starlette/_exception_handler.py:42: in wrapped_app
    await app(scope, receive, sender)
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:116: in app
    response = await f(request)
               ^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:670: in app
    raw_response = await run_endpoint_function(
/usr/local/lib/python3.11/site-packages/fastapi/routing.py:326: in run_endpoint_function
    return await run_in_threadpool(dependant.call, **values)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/starlette/concurrency.py:32: in run_in_threadpool
    return await anyio.to_thread.run_sync(func)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/to_thread.py:63: in run_sync
    return await get_async_backend().run_sync_in_worker_thread(
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:2502: in run_sync_in_worker_thread
    return await future
           ^^^^^^^^^^^^
/usr/local/lib/python3.11/site-packages/anyio/_backends/_asyncio.py:986: in run
    result = context.run(func, *args)
             ^^^^^^^^^^^^^^^^^^^^^^^^
backend/routes.py:24: in post_runs
    run_id = uuid.uuid4().str
             ^^^^^^^^^^^^^^^^
E   AttributeError: 'UUID' object has no attribute 'str'
=========================== short test summary info ============================
FAILED tests/test_runs.py::test_create_run_success - AttributeError: 'UUID' o...
FAILED tests/test_runs.py::test_list_runs_contains_created - AttributeError: ...
FAILED tests/test_runs.py::test_get_run_detail - AttributeError: 'UUID' objec...
FAILED tests/test_runs.py::test_join_run_success - AttributeError: 'UUID' obj...
FAILED tests/test_runs.py::test_join_run_duplicate_rejected - AttributeError:...
FAILED tests/test_runs.py::test_join_run_empty_name - AttributeError: 'UUID' ...
FAILED tests/test_runs.py::test_leave_run_success - AttributeError: 'UUID' ob...
FAILED tests/test_runs.py::test_leave_run_participant_not_found - AttributeEr...
FAILED tests/test_runs.py::test_leave_run_empty_name - AttributeError: 'UUID'...
9 failed, 2 passed in 1.29s

```


## Error

frontend (non-blocking): no test files provided

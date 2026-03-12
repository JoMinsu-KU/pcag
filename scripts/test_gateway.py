import httpx

for asset in ['reactor_01', 'robot_arm_01', 'agv_01']:
    try:
        resp = httpx.get(f'http://localhost:8003/v1/assets/{asset}/snapshots/latest', timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            print(f'{asset}:')
            print(f'  sensor_snapshot: {data["sensor_snapshot"]}')
            print(f'  hash: {data["sensor_snapshot_hash"][:20]}...')
            print(f'  reliability: {data["sensor_reliability_index"]}')
            print()
        else:
            print(f'{asset}: Status Code {resp.status_code}')
            print(resp.text)
    except Exception as e:
        print(f'{asset}: ERROR - {e}')

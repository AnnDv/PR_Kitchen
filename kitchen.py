import queue
import threading
import time
from flask import Flask, request
import requests
import config as config

app = Flask(__name__)

@app.route('/order', methods=['POST'])
def order():
    data = request.get_json()
    print(f'New order sent to kitchen server {data["order_id"]}')
    split_order(data)
    return {'isSuccess': True}

def split_order(data):
    kitchen_order = {
        'order_id': data['order_id'],
        'table_id': data['table_id'],
        'waiter_id': data['waiter_id'],
        'items': data['items'],
        'priority': int(data['priority']),
        'max_wait': data['max_wait'],
        'received_time': time.time(),
        'cooking_details': queue.Queue(),
        'is_done_counter': 0,
        'time_start': data['time_start'],
    }

    config.ORDERS.append(kitchen_order)
    for item_id in data['items']:
        food = next((f for i, f in enumerate(config.FOOD_LIST) if f['id'] == item_id), None)
        if food is not None:
            config.FOOD_Q.put_nowait({
                'food_id': food['id'],
                'order_id': data['order_id'],
            })

def cooking_process(cook, food_items: queue.Queue):
    while True:
        try:
            food_item = food_items.get_nowait()
            food_details = next((f for f in config.MENU if f['id'] == food_item['food_id']), None)
            (idx, order_details) = next(((idx, order) for idx, order in enumerate(config.ORDERS) if order['order_id'] == food_item['order_id']), (None, None))
            len_order_items = len(config.ORDERS[idx]['items'])
            # check if cook can afford to do this type of food
            if food_details['complexity'] == cook['rank'] or food_details['complexity'] == cook['rank'] - 1:
                print(f'{threading.current_thread().name} cooking food {food_details["name"]}: with Id {food_details["id"]} for order {order_details["order_id"]}')
                time.sleep(food_details['preparation-time'] * config.TIME_UNIT)
                config.ORDERS[idx]['prepared_items'] += 1
                if config.ORDERS[idx]['prepared_items'] == len_order_items:
                    print(f'{threading.current_thread().name} cook has finished the order {order_details["order_id"]}')
                    config.ORDERS[idx]['cooking_details'].put({'food_id': food_details['id'], 'cook_id': cook['id']})
                    finish_preparation_time = int(time.time())
                    print(f'Calculating')
                    payload = {
                        **config.ORDERS[idx],
                        'cooking_time': finish_preparation_time - int(config.ORDERS[idx]['received_time']),
                        'cooking_details': list(config.ORDERS[idx]['cooking_details'].queue)
                    }
                    requests.post('http://localhost:8000/distribution', json=payload, timeout=0.0000000001)

            else:
                food_items.put_nowait(food_item)

        except Exception as e:
            pass

def chefs_multitasking_process(cook, food_items):
    for i in range(cook['proficiency']):
        hand_thread = threading.Thread(target=cooking_process, args=(cook, food_items,), daemon=True, name=f'{cook["name"]}-Task {i}')
        hand_thread.start()


def run_kitchen_server():
    main_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False), daemon=True)
    main_thread.start()

    for _, cook in enumerate(config.CHEFS_LIST):
        cook_thread = threading.Thread(target=chefs_multitasking_process, args=(cook, config.MENU,), daemon=True)
        cook_thread.start()

    while True:
        pass

if __name__ == '__main__':
    run_kitchen_server()

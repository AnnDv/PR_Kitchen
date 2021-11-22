import queue
import threading
import time
from itertools import count
from flask import Flask, request
import requests
import config as config
from operator import itemgetter

counter = count(start=1, step=1)
app = Flask(__name__)

@app.route('/order', methods=['POST'])
def order():
    data = request.get_json()
    print(f'New order sent to kitchen server {data["order_id"]} items : {data["items"]} priority : {data["priority"]}')
    split_order(data)
    return {'isSuccess': True}

def split_order(input_order):
    priority = (-int(input_order['priority']))
    kitchen_order = {
        'order_id': input_order['order_id'],
        'table_id': input_order['table_id'],
        'waiter_id': input_order['waiter_id'],
        'items': input_order['items'],
        'priority': priority,
        'max_wait': input_order['max_wait'],
        'received_time': time.time(),
        'cooking_details': queue.Queue(),
        'prepared_items': 0,
        'time_start': input_order['time_start'],
    }
    config.ORDERS.append(kitchen_order)
    # split the order in item queue available for chefs
    for idx in input_order['items']:
        food_item = next((f for i, f in enumerate(config.MENU) if f['id'] == idx), None)
        if food_item is not None:
            config.FOOD_Q.put_nowait((priority, next(counter),{
                'food_id': food_item['id'],
                'order_id': input_order['order_id'],
                'priority': int(input_order['priority'])
            }))

def cooking_process(cook, stoves: queue.Queue, ovens: queue.Queue, food_items: queue.PriorityQueue):
    while True:
        try:
            item = food_items.get_nowait()
            food_item = item[2]
            curr_counter = item[1]
            food_details = next((f for f in config.MENU if f['id'] == food_item['food_id']), None)
            (idx, order_details) = next(((idx, order) for idx, order in enumerate(config.ORDERS) if order['order_id'] == food_item['order_id']), (None, None))
            len_order_items = len(config.ORDERS[idx]['items'])

            # check if cook can afford to do this type of food
            if food_details['complexity'] == cook['rank'] or food_details['complexity'] == cook['rank'] - 1:
                cooking_apparatus = food_details['cooking-apparatus']

                if cooking_apparatus is None:
                    print(f'{threading.current_thread().name} cooking food {food_details["name"]}: with id {food_details["id"]} for order {order_details["order_id"]} manually')
                    time.sleep(food_details['preparation-time'] * config.TIME_UNIT)
                    print(f'{threading.current_thread().name} finished cooking food {food_details["name"]}: with id {food_details["id"]} for order {order_details["order_id"]} manually')

                elif cooking_apparatus == 'oven':
                    oven = ovens.get_nowait()
                    print(f'{threading.current_thread().name} cooking food {food_details["name"]}: with id {food_details["id"]} for order {order_details["order_id"]} on oven {oven}')
                    time.sleep(food_details['preparation-time'] * config.TIME_UNIT)
                    length = ovens.qsize()
                    ovens.put_nowait(length)
                    print(f'{threading.current_thread().name} finished cooking food {food_details["name"]}: with id {food_details["id"]} for order {order_details["order_id"]} on oven {oven}')
                
                elif cooking_apparatus == 'stove':
                    stove = stoves.get_nowait()
                    print(f'{threading.current_thread().name} cooking food {food_details["name"]}: with id {food_details["id"]} for order {order_details["order_id"]} on stove {stove}')
                    time.sleep(food_details['preparation-time'] * config.TIME_UNIT)
                    length = stoves.qsize()
                    stoves.put_nowait(length)
                    print(f'{threading.current_thread().name} finished cooking food {food_details["name"]}: with id {food_details["id"]} for order {order_details["order_id"]} on stove {stove}')

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
                food_items.put_nowait((food_item['priority'], curr_counter, food_item))

        except Exception as e:
            pass

def cooks_multitasking_process(cook, ovens, stoves, food_items):
    for i in range(cook['proficiency']):
        task_thread = threading.Thread(target=cooking_process, args=(cook, ovens, stoves, food_items,), daemon=True, name=f'{cook["name"]}-Task {i}')
        task_thread.start()

def run_kitchen_server():
    main_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False), daemon=True)
    main_thread.start()

    for _, cook in enumerate(config.CHEFS_LIST):
        cook_thread = threading.Thread(target=cooks_multitasking_process, args=(cook, config.OVENS_Q, config.STOVES_Q, config.FOOD_Q), daemon=True)
        cook_thread.start()

    while True:
        pass

if __name__ == '__main__':
    run_kitchen_server()

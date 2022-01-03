from app import app
from flask import request
from flask import jsonify

import json
import requests
from state import State
import logging
import sys
import _thread
import threading 
import copy
import concurrent.futures

global state
@app.before_first_request
def build_state():
    global state
    state = State()

################################################ Helper Functions ###############################################################

def sender(location, extension, key, request_type, payload):
    resp = ""
    if request_type == "p":
        resp = requests.put(f'http://{location}/{extension}/{key}', json=payload, timeout=120, headers = {"Content-Type": "application/json"})
    elif request_type == "g":
        resp = requests.get(f'http://{location}/{extension}/{key}', json = payload, timeout=120, headers = {"Content-Type": "application/json"})
    elif request_type == "d":
        resp = requests.delete(f'http://{location}/{extension}/{key}', json = payload, timeout=120, headers = {"Content-Type": "application/json"})
    elif request_type == "v":
        resp = requests.put(f'http://{location}/{extension}', json = payload, timeout=120, headers = {"Content-Type": "application/json"})
    elif request_type == "s":
        resp = requests.get(f'http://{location}/{extension}',timeout=120, headers = {"Content-Type": "application/json"})
    elif request_type == "dd":
        resp = requests.put(f'http://{location}/{extension}',timeout=120, headers = {"Content-Type": "application/json"})
    elif request_type == "r":
        resp = requests.get(f'http://{location}/{extension}',timeout=120, headers = {"Content-Type": "application/json"})

    resp_data = resp.json()
    return resp_data, resp.status_code

def full_send(addr, route):
    global state
    fail_flag = False
    delete_dict = copy.deepcopy(state.storage)
    for key in delete_dict:
        payload = {"value":state.storage[key],"address":state.address}
        del state.storage[key]
        response = sender(addr,route,key,"p",payload)
        if response[1] != 200 and response[1] != 201: fail_flag = True
    if fail_flag: return json.dumps({"message":"Redistribution of data unsuccessful."}), 500            
    return json.dumps({"message":"Redistribution of data successful."}), 200

def ring_traversal(payload, key, key_hash_id, reqType):
    global state

    if len(state.view) == 1 and state.view[0] == state.address: return sender(state.view[0],"store_key",key,reqType,payload)
    if key_hash_id in state.set_of_local_ids: return sender(state.address,"store_key",key,reqType,payload) 
    if key_hash_id < state.finger_table[0][0]:
        if (key_hash_id < state.lowest_hash_id) and (key_hash_id < state.predecessor[0]) and (state.predecessor[0] > state.lowest_hash_id):
            return sender(state.address,"store_key",key,reqType,payload)
        elif key_hash_id < state.lowest_hash_id: return sender(state.predecessor[1],"kvs/keys",key,reqType,payload)
        else: return sender(state.finger_table[0][1],"store_key",key,reqType,payload)
    if key_hash_id > state.finger_table[-1][0]:
        if state.finger_table[-1][0] == state.max_address[0]: 
            return sender(state.min_address[1],"store_key",key,reqType,payload)
        else: return sender(state.finger_table[-1][1],"kvs/keys",key,reqType,payload)
    if len(state.finger_table) > 1:
        bounds = state.maps_to(key_hash_id)
        if bounds["upper bound"][2] == 1:
            pred_of_first_finger = state.immediate_pred(bounds["upper bound"][0])
            if key_hash_id > pred_of_first_finger and key_hash_id <= bounds["upper bound"][0]:
                return sender(bounds["upper bound"][1],"store_key",key,reqType,payload)
            elif key_hash_id > pred_of_first_finger and bounds["upper bound"][0] < bounds["lower bound"][0]:
                return sender(bounds["upper bound"][1],"store_key",key,reqType,payload)
            else: return sender(bounds["lower bound"][1],"kvs/keys",key,reqType,payload)
        else: return sender(bounds["lower bound"][1],"kvs/keys",key,reqType,payload)
    else: return sender(state.finger_table[0][1],"kvs/keys",key,reqType,payload)
    return json.dumps({"message":"Server is down!"}), 400 

    
################################################### View Change Endpoints #######################################################################

@app.route('/kvs/view-change', methods=['PUT'])
def view_change():
    global state
    view_str = request.get_json()["view"]
    view_list = sorted(view_str.split(','))
    payload = {"view":view_list}
    state_view_set = set(state.view)
    new_view_set   = set(view_list)
    broadcast_set  = new_view_set.union(state_view_set)
    #Broadcasting the view
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(sender,address,"view-change-action",None,"v",payload) for address in broadcast_set]
    result_collection = [f.result() for f in futures]
    for x in range(len(result_collection)):
        if result_collection[x][1] != 200:
            return json.dumps({"message":"View change unsuccessful."}), 500
    #Triggering the redistribution of data
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(sender,address,"distribute_data",None,"dd",{}) for address in broadcast_set]
    result_collection = [f.result() for f in futures]
    for x in range(len(result_collection)):
        if result_collection[x][1] != 200:
            return json.dumps({"message":"View change unsuccessful."}), 500
    state.data_structure_clear(3)
    #Polling the shards and gathering the key-counts
    shards = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(sender,view_list[x],"kvs/key-count",None,"s",None) for x in range(len(view_list))]
    result_collection = [f.result() for f in futures]
    for x in range(len(result_collection)):
        shards.append({"address":view_list[x],"key-count":result_collection[x][0]["key-count"]})
    return json.dumps({"message":"View change successful","shards":shards}), 200

@app.route('/view-change-action', methods=['PUT'])
def view_change_action():
    global state
    state.previous_view = copy.deepcopy(state.view)
    state.view = request.get_json()["view"]
    state.data_structure_clear(2)
    if state.address in state.view: state.gen_finger_table(state.view)
    return json.dumps({"message":"View received and finger table generated."}), 200

@app.route('/distribute_data', methods=['PUT'])
def data_distribute():

    global state
    if state.view == state.previous_view: return json.dumps({"message": "Redistribution of data successful."}), 200
    if len(state.view) == 1: return full_send(state.view[0], "store_key")
    local_addr_in_view = state.address in state.view
    if not local_addr_in_view: return full_send(state.view[0], "kvs/keys")
    if local_addr_in_view:
        set_of_ranges = []
        for x in range(len(state.list_of_local_ids_and_preds)):
            if state.list_of_local_ids_and_preds[x] in state.previous_local_ids_and_preds:
                set_of_ranges.append(state.list_of_local_ids_and_preds[x])
        if len(set_of_ranges) == 0: return full_send(state.address, "kvs/keys")
        if len(set_of_ranges) >= 1:
            delete_dict = copy.deepcopy(state.storage)
            for key in delete_dict:
                key_hash_id = state.hash_key(key)
                key_belongs_here = state.find_range(key_hash_id, set_of_ranges)
                if not key_belongs_here:
                    payload = {"value":state.storage[key]}
                    del state.storage[key]
                    resp = sender(state.address,"kvs/keys",key,"p",payload)
                    if resp[1] != 200 and resp[1] != 201: return json.dumps({"message":"Redistribution of data unsuccessful."})
        return json.dumps({"message":"Redistribution of data successful."}), 200
                
########################################### Key Value Store Endpoints ######################################################

@app.route('/kvs/keys/<key>', methods=['PUT'])
def handle_put(key):
    data = request.get_json()
    if "value" not in data: return json.dumps({"error":"Value is missing","message":"Error in PUT"}), 400
    if len(key) > 50 : return json.dumps({"error":"Key is too long","message":"Error in PUT"}), 400

    global state 
    key_hash_id,payload               = state.hash_key(key),{}
    payload["value"],address_present  = data["value"],"address" in data
    payload["address"]                = data["address"] if address_present else state.address
    
    return ring_traversal(payload, key, key_hash_id, "p")

@app.route('/kvs/keys/<key>', methods=['GET'])
def handle_get(key):
    global state 
    key_hash_id,payload,data = state.hash_key(key),{},request.get_json()
    address_present = "address" in data
    payload["address"] = data["address"] if address_present else state.address

    return ring_traversal(payload, key, key_hash_id, "g")
    
@app.route('/kvs/keys/<key>', methods=['DELETE'])
def handle_delete(key):
    global state 
    key_hash_id,payload,data = state.hash_key(key),{},request.get_json()
    address_present = "address" in data
    payload["address"] = data["address"] if address_present else state.address

    return ring_traversal(payload, key, key_hash_id, "d")
    
######################### Storage Management Endpoints (final destinations muahahaha) ##################################

@app.route('/store_key/<key>', methods=['PUT'])
def store(key):
    global state
    data = request.get_json()

    if "replication" not in data:
        app.logger.info("hello from replication block in store()")
        broadcast_set = [shard_mate for shard_mate in state.local_shard_list if shard_mate != state.address]
        data["replication"] = True
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [executor.submit(sender,address,"store_key",key,"p",data) for address in broadcast_set]
        # result_collection = [f.result() for f in futures]
        # for x in range(len(result_collection)):
        #     if result_collection[x][1] != 200:
        #         return json.dumps({"message":"Data replication not fully successful."}), 500

    replace = key in state.storage

    if replace: 
        local_addr_is_greater = state.storage[key]["address"] > data["address"]
        if(not local_addr_is_greater): state.storage[key] = {"value": data["value"], "address":data["address"]}
    if not replace:    
        state.storage[key] = {"value": data["value"], "address":data["address"]}
    
    message     = "Updated successfully" if replace else "Added successfully"
    status_code = 200 if replace else 201
    if data["address"] == state.address: return json.dumps({"message":message,"replaced":replace}), status_code
    else: return json.dumps({"message":message,"replaced":replace,"address":state.address}), status_code

@app.route('/store_key/<key>', methods=['GET'])
def retrieve(key):
    global state
    data = request.get_json()
    data_present = key in state.storage
    if data_present: 
        if data["address"] == state.address:
            return json.dumps({"doesExist":True, "message":"Retrieved successfully", "value": state.storage[key]["value"]}), 200
        return json.dumps({"doesExist":True,"message":"Retrieved successfully","value":state.storage[key]["value"],"address":state.address}) 
    return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in GET"}), 404

@app.route('/store_key/<key>', methods=['DELETE'])
def delete(key):
    global state
    data = request.get_json()
    data_present = key in state.storage
    if data_present: 
        del state.storage[key]
        if data["address"] == state.address:
            return json.dumps({"doesExist":True, "message":"Deleted successfully"}), 200
        return json.dumps({"doesExist":True,"message":"Deleted successfully","address":state.address}) 
    return json.dumps({"doesExist":False,"error":"Key does not exist","message":"Error in DELETE"}), 404

######################################## Administrative Endpoints ##############################################

@app.route('/recon', methods=['GET'])
def recon():
    global state
    array = []
    state.cl.moveHead()
    
    for _ in range(state.cl.getLength()):
        array.append(state.cl.getCursorData())
        state.cl.moveNext()
    return json.dumps({"local address":state.address,"linked list data":array,"length of linked list":state.cl.getLength(),"state.view":state.view, "finger table":state.finger_table,"length of finger table":len(state.finger_table),"map":state.map,"state.storage":state.storage})

@app.route('/data_request/<key>', methods=['GET'])
def get(key):
    id = state.hash_key(key)
    #address = state.maps_to(id)

    return json.dumps({"key hash id":id,"lowest_hash_id":state.lowest_hash_id,"lowest hash id's predecessor":state.predecessor,"here's the key_local_ids_and_preds":state.list_of_local_ids_and_preds}), 200

@app.route('/view_request', methods=["GET"])
def return_view():
    global state
    return json.dumps({"state.view":state.view}), 200
    
@app.route('/kvs/key-count', methods=['GET'])
def count():
    global state
    return json.dumps({"message":"Key count retrieved successfully","key-count":len(state.storage.keys())}), 200 

@app.route('/all_hash_ids', methods=["GET"])
def hash_ids():
    global state
    hash_id_dict = {}
    for key in state.storage:
        hash_id = state.hash_key(key)
        hash_id_dict[key] = hash_id
    return json.dumps({"local node address: ":state.address,"all hash ids present in this node's storage: ":hash_id_dict})

@app.route('/shard_list_test', methods=["POST", "GET"])
def sas_test():
    
    return json.dumps({"global shard list":state.complete_shard_list, "local_shard_list":state.local_shard_list, "local shard number":state.shard_num}), 200

    






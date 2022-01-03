#!/bin/bash

docker run -p 13804:13800 --net=kv_subnet --ip=10.10.0.7 --name="node4" -e ADDRESS="10.10.0.7:13800" -e VIEW="10.10.0.4:13800,10.10.0.5:13800,10.10.0.6:13800,10.10.0.7:13800,10.10.0.8:13800" -e REPLFACTOR=2 kvs

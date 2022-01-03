#!/bin/bash

curl --request PUT \
 --header "Content-Type: application/json" \
 --write-out "%{http_code}\n" \
 --data '{"value":149}' \
 http://localhost:13802/kvs/keys/b

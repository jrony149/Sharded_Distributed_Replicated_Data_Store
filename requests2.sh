#!/bin/bash

curl --request GET \
 --header "Content-Type: application/json" \
 --write-out "%{http_code}\n" \
 http://localhost:13801/shard_list_test

echo "--------------------------------------------------------------------------------------------"

#curl --request GET \
#--header "Content-Type: application/json" \
#--write-out "%{http_code}\n" \
# http://localhost:13802/recon
#
#echo "--------------------------------------------------------------------------------------------"

#curl --request GET \
#--header "Content-Type: application/json" \
#--write-out "%{http_code}\n" \
# http://localhost:13803/recon

#echo "--------------------------------------------------------------------------------------------"

#curl --request GET \
# --header "Content-Type: application/json" \
# --write-out "%{http_code}\n" \
# http://localhost:13804/recon

#echo "--------------------------------------------------------------------------------------------"

#curl --request GET \
# --header "Content-Type: application/json" \
# --write-out "%{http_code}\n" \
# http://localhost:13805/recon

#echo "--------------------------------------------------------------------------------------------"

#curl --request GET \
# --header "Content-Type: application/json" \
# --write-out "%{http_code}\n" \
# http://localhost:13806/kvs/keys/v

#echo "--------------------------------------------------------------------------------------------"

#curl --request GET \
# --header "Content-Type: application/json" \
# --write-out "%{http_code}\n" \
# http://localhost:13807/kvs/keys/v

#echo "--------------------------------------------------------------------------------------------"

#curl --request GET \
# --header "Content-Type: application/json" \
# --write-out "%{http_code}\n" \
# http://localhost:13808/kvs/keys/v

#echo "--------------------------------------------------------------------------------------------"

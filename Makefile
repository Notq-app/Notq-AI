# Variables
IMAGE_NAME=notq-ai
IMAGE_TAG=latest
SWR_REGISTRY=swr.ap-southeast-3.myhuaweicloud.com
SWR_NAMESPACE=notq
SWR_IMAGE=$(SWR_REGISTRY)/$(SWR_NAMESPACE)/$(IMAGE_NAME):$(IMAGE_TAG)

# Replace with secrets later
SWR_USERNAME=ap-southeast-3@HST3WGJ0JVPI75N0R2LJ
SWR_PASSWORD=80d559b743a537c7a303f3750063d41aaf6356b5a7717b9c46b9cf4009e8e3e9

.PHONY: build tag login push deploy stl main

# Step 1 - Build
build:
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .

# Step 2 - Tag
tag:
	docker tag $(IMAGE_NAME):$(IMAGE_TAG) $(SWR_IMAGE)

# Step 3 - Login
login:
	docker login -u $(SWR_USERNAME) -p $(SWR_PASSWORD) $(SWR_REGISTRY)

# Step 4 - Push
push:
	docker push $(SWR_IMAGE)

# All in one
deploy: build tag login push

# Run streamlit locally
stl:
	streamlit run streamlit.py

# Run main locally
main:
	python main.py

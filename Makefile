IMAGE_NAME ?= notq-ai
REGISTRY ?= ghcr.io/notq-app

TAG ?= latest
IMAGE := $(IMAGE_NAME):$(TAG)
REMOTE_IMAGE := $(REGISTRY)/$(IMAGE_NAME):$(TAG)

.PHONY: build tag push deploy

build:
	docker build -t $(IMAGE) .

tag:
	docker tag $(IMAGE) $(REMOTE_IMAGE)

push:
	docker push $(REMOTE_IMAGE)

deploy: build tag push

stl:
	streamlit run streamlit.py

main:
	python main.py
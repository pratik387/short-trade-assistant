# Docker Compose Commands for Trading Assistant

This README contains useful Docker Compose commands for building, running, and managing the `trading-backend` and `trading-frontend` services.

## 🔧 Build

- **Rebuild all images**
  ```bash
  docker-compose build
  ```
  Rebuilds all service images.

- **Rebuild just the frontend**
  ```bash
  docker-compose build frontend
  ```
  Rebuilds only the frontend image.

- **Rebuild just the backend**
  ```bash
  docker-compose build backend
  ```
  Rebuilds only the backend image.

## ▶️ Start / Run

- **Start all services (detached)**
  ```bash
  docker-compose up -d
  ```
  Launches all services in the background.

- **Start with fresh builds**
  ```bash
  docker-compose up -d --build
  ```
  Rebuilds images and starts services.

- **Start only frontend (no dependencies)**
  ```bash
  docker-compose up -d --no-deps --build frontend
  ```
  Rebuilds and restarts only the frontend service.

- **Start only backend (no dependencies)**
  ```bash
  docker-compose up -d --no-deps --build backend
  ```
  Rebuilds and restarts only the backend service.

## 🛑 Stop / Shutdown

- **Stop & remove containers and networks**
  ```bash
  docker-compose down
  ```
  Stops services and removes containers and networks (volumes retained).

- **Stop without removing containers**
  ```bash
  docker-compose stop
  ```
  Stops services but leaves containers intact.

- **Stop just the frontend**
  ```bash
  docker-compose stop frontend
  ```
  Stops only the frontend service.

## 🔄 Restart

- **Restart frontend**
  ```bash
  docker-compose restart frontend
  ```
  Restarts the frontend container.

- **Restart backend**
  ```bash
  docker-compose restart backend
  ```
  Restarts the backend container.

## 📋 Logs & Inspection

- **Tail logs for both services**
  ```bash
  docker-compose logs -f
  ```
  Follows logs for all services.

- **Tail backend logs only**
  ```bash
  docker-compose logs -f backend
  ```
  Follows logs for the backend service.

- **Tail frontend logs only**
  ```bash
  docker-compose logs -f frontend
  ```
  Follows logs for the frontend service.

- **List service status & ports**
  ```bash
  docker-compose ps
  ```
  Displays status and port mappings.

- **Live resource usage**
  ```bash
  docker stats
  ```
  Shows live container resource usage.

- **Execute shell in backend**
  ```bash
  docker-compose exec backend bash
  ```
  Opens an interactive shell in the backend container.

## 🧹 Cleanup & Extras

- **Recreate service without using cache**
  ```bash
  docker-compose up -d --no-deps --force-recreate backend
  ```
  Forces recreation of the backend container without using cache.

- **Remove volumes**
  ```bash
  docker-compose down -v
  ```
  Removes all named volumes.

- **Prune unused images**
  ```bash
  docker image prune
  ```
  Deletes dangling images to free up space.

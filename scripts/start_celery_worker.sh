#!/bin/bash
# Start Celery worker for Ollama Coder batch processing

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Ollama Coder - Celery Worker Startup${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if Celery is installed
if ! python3 -c "import celery" 2>/dev/null; then
    echo -e "${RED}Error: Celery not installed${NC}"
    echo -e "${YELLOW}Install with: uv pip install -e '.[celery]'${NC}"
    exit 1
fi

# Check if Redis is running (if using Redis)
if [ -z "$CELERY_BROKER_URL" ] || [[ "$CELERY_BROKER_URL" == redis://* ]]; then
    echo -e "${YELLOW}Checking Redis connection...${NC}"
    if ! redis-cli ping > /dev/null 2>&1; then
        echo -e "${RED}Warning: Redis not responding${NC}"
        echo -e "${YELLOW}Start Redis with: docker run -d -p 6379:6379 redis${NC}"
    else
        echo -e "${GREEN}✓ Redis is running${NC}"
    fi
fi

# Default configuration
WORKER_NAME="${WORKER_NAME:-worker1}"
CONCURRENCY="${CONCURRENCY:-4}"
LOGLEVEL="${LOGLEVEL:-info}"
QUEUES="${QUEUES:-default,agent_tasks,validation,tests,mcp_operations}"

# Export environment variables if not set
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-redis://localhost:6379/0}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-redis://localhost:6379/0}"

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Worker Name: $WORKER_NAME"
echo "  Concurrency: $CONCURRENCY"
echo "  Log Level: $LOGLEVEL"
echo "  Queues: $QUEUES"
echo "  Broker: $CELERY_BROKER_URL"
echo "  Result Backend: $CELERY_RESULT_BACKEND"
echo ""

# Start Celery worker
echo -e "${GREEN}Starting Celery worker...${NC}"
echo ""

celery -A ollama_coder.batch.celery_app worker \
    --hostname="$WORKER_NAME@%h" \
    --concurrency="$CONCURRENCY" \
    --loglevel="$LOGLEVEL" \
    -Q "$QUEUES" \
    --max-tasks-per-child=100 \
    --time-limit=3600 \
    --soft-time-limit=3300

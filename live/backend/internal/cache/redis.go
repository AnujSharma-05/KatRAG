package cache

import (
	"context"
	"encoding/json"
	"log"
	"time"

	"github.com/redis/go-redis/v9"
)

var Client *redis.Client

// InitRedis connects to the Redis server
func InitRedis(addr, password string, db int) {
	Client = redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password, // no password set
		DB:       db,       // use default DB
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := Client.Ping(ctx).Result()
	if err != nil {
		log.Fatalf("Failed to connect to Redis: %v", err)
	}
	log.Println("Connected to Redis successfully!")
}

// Set Scope JSON to Redis with a 60-second TTL
func SetScope(ctx context.Context, userID string, scopeData map[string]interface{}) error {
	bytes, err := json.Marshal(scopeData)
	if err != nil {
		return err
	}
	return Client.Set(ctx, "scope:"+userID, bytes, 60*time.Second).Err()
}

// Get Scope JSON from Redis
func GetScope(ctx context.Context, userID string) (map[string]interface{}, error) {
	val, err := Client.Get(ctx, "scope:"+userID).Result()
	if err == redis.Nil {
		return nil, nil // Cache miss
	} else if err != nil {
		return nil, err
	}

	var scopeData map[string]interface{}
	err = json.Unmarshal([]byte(val), &scopeData)
	if err != nil {
		return nil, err
	}
	return scopeData, nil
}

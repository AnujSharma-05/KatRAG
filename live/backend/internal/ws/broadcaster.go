package ws

import (
	"log"
	"strconv"
	"sync"

	"github.com/AnujSharma-05/KatRAG/live/backend/internal/auth"

	"github.com/gofiber/fiber/v2"
	"github.com/gofiber/websocket/v2"
)

type Broadcaster struct {
	mu          sync.RWMutex
	connections map[int][]*websocket.Conn
}

var GlobalBroadcaster = &Broadcaster{
	connections: make(map[int][]*websocket.Conn),
}

func (b *Broadcaster) AddConnection(groupID int, conn *websocket.Conn) {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.connections[groupID] = append(b.connections[groupID], conn)
	log.Printf("WS: Added connection to group %d. Total connections: %d", groupID, len(b.connections[groupID]))
}

func (b *Broadcaster) RemoveConnection(groupID int, conn *websocket.Conn) {
	b.mu.Lock()
	defer b.mu.Unlock()
	conns := b.connections[groupID]
	for i, c := range conns {
		if c == conn {
			b.connections[groupID] = append(conns[:i], conns[i+1:]...)
			break
		}
	}
	log.Printf("WS: Removed connection from group %d", groupID)
}

func (b *Broadcaster) Broadcast(groupID int, message []byte) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	conns, ok := b.connections[groupID]
	if !ok {
		return
	}
	for _, c := range conns {
		if err := c.WriteMessage(websocket.TextMessage, message); err != nil {
			log.Printf("WS: Error writing message to group %d: %v", groupID, err)
		}
	}
}

// WebsocketUpgradeMiddleware checks if the request is a websocket upgrade
func WebsocketUpgradeMiddleware(c *fiber.Ctx) error {
	if websocket.IsWebSocketUpgrade(c) {
		c.Locals("allowed", true)
		return c.Next()
	}
	return fiber.ErrUpgradeRequired
}

// GroupWSHandler handles the upgraded websocket connection
func GroupWSHandler(c *websocket.Conn) {
	groupIDStr := c.Params("id")
	groupID, err := strconv.Atoi(groupIDStr)
	if err != nil {
		log.Println("WS: Invalid group ID")
		c.Close()
		return
	}

	// Ideally we validate JWT here from query param or a prior middleware that sets Locals
	// For now, assume it's authorized if we reach here (assuming middleware is attached before)
	GlobalBroadcaster.AddConnection(groupID, c)
	defer GlobalBroadcaster.RemoveConnection(groupID, c)

	for {
		mt, msg, err := c.ReadMessage()
		if err != nil {
			log.Println("WS Error/Close:", err)
			break
		}
		log.Printf("WS message received from group %d (type %d): %s", groupID, mt, msg)
	}
}

// RegisterWSRoute registers the websocket endpoints on the Fiber app
func RegisterWSRoute(app *fiber.App) {
	// Require JWT and valid websocket upgrade before accepting
	app.Use("/groups/:id/ws", auth.JWTMiddleware, WebsocketUpgradeMiddleware)
	app.Get("/groups/:id/ws", websocket.New(GroupWSHandler))
}

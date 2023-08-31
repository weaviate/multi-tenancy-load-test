package main

import (
	"context"
	"fmt"
	"github.com/weaviate/weaviate-go-client/v4/weaviate"
	"github.com/weaviate/weaviate/entities/models"
	"log"
	"math/rand"
	"sync"
	"time"
)

var ClassName = "MultiTenancyTest"

func main() {
	log.Println("Script started")
	cfg := weaviate.Config{
		Host:   "localhost:8080",
		Scheme: "http",
	}
	client, err := weaviate.NewClient(cfg)
	if err != nil {
		fmt.Println("Failed to fetch tenants:", err)
		return
	}

	tenants, err := fetchAllTenants(client)
	if err != nil {
		fmt.Println("Failed to fetch tenants:", err)
		return
	}

	var wg sync.WaitGroup
	errorCh := make(chan error, 1000)

	sleepTime := 500 * time.Millisecond
	for i := 0; i < 1000; i++ {
		randomTenant := tenants[rand.Intn(len(tenants))]
		wg.Add(1)
		go func(tenant string) {
			defer wg.Done()
			err := simulateUser(client, tenant)
			if err != nil {
				log.Printf("Error for tenant %s: %s\n", tenant, err)
				errorCh <- err
			}
		}(randomTenant)

		time.Sleep(sleepTime)

		if i%10 == 9 && sleepTime > 10*time.Millisecond {
			sleepTime -= 5 * time.Millisecond
		}
	}

	wg.Wait()
	close(errorCh)

	for err := range errorCh {
		if err != nil {
			fmt.Println("Error:", err)
		}
	}
	log.Println("Script completed")
}

func fetchAllTenants(client *weaviate.Client) ([]string, error) {
	tenants, err := client.Schema().TenantsGetter().WithClassName(ClassName).Do(context.Background())
	if err != nil {
		return nil, err
	}

	names := make([]string, len(tenants))
	for i, tenant := range tenants {
		names[i] = tenant.Name
	}

	return names, nil
}

func simulateUser(client *weaviate.Client, tenant string) error {
	log.Printf("Simulating user for tenant: %s\n", tenant)
	if err := activateTenant(client, tenant); err != nil {
		return fmt.Errorf("failed to activate tenant %s: %w", tenant, err)
	}

	endTime := time.Now().Add(1 * time.Minute)
	for time.Now().Before(endTime) {
		if _, err := runQueryUsingNearVector(client, tenant); err != nil {
			return fmt.Errorf("query using near vector failed for tenant %s: %w", tenant, err)
		}
		time.Sleep(time.Duration(rand.Intn(5000)+1000) * time.Millisecond)
	}

	if err := disableTenant(client, tenant); err != nil {
		return fmt.Errorf("failed to disable tenant %s: %w", tenant, err)
	}

	return nil
}

func activateTenant(client *weaviate.Client, tenant string) error {
	startTime := time.Now()
	err := client.Schema().TenantsUpdater().WithClassName(ClassName).WithTenants(models.Tenant{
		ActivityStatus: "HOT",
		Name:           tenant,
	}).Do(context.Background())
	duration := time.Since(startTime).Milliseconds() // This gives the duration in seconds
	if err == nil {
		log.Printf("Activated tenant: %s in %dms\n", tenant, duration)
	}
	return err
}

func runQueryUsingNearVector(client *weaviate.Client, tenant string) (*models.GraphQLResponse, error) {
	startTime := time.Now()
	nearVector := client.GraphQL().NearVectorArgBuilder().WithVector(randomVector(1536))
	response, err := client.GraphQL().Get().WithClassName(ClassName).WithTenant(tenant).WithNearVector(nearVector).Do(context.Background())
	duration := time.Since(startTime).Milliseconds()
	if err == nil {
		log.Printf("Ran query for tenant: %s in %dms\n", tenant, duration)
	}
	return response, err
}

func disableTenant(client *weaviate.Client, tenant string) error {
	startTime := time.Now()
	err := client.Schema().TenantsUpdater().WithClassName(ClassName).WithTenants(models.Tenant{
		ActivityStatus: "COLD",
		Name:           tenant,
	}).Do(context.Background())
	duration := time.Since(startTime).Milliseconds()
	if err == nil {
		log.Printf("Deactivated tenant: %s in %dms\n", tenant, duration)
	}
	return err
}

func randomVector(dimensions int) []float32 {
	rand.Seed(time.Now().UnixNano())
	vector := make([]float32, dimensions)
	for i := range vector {
		vector[i] = rand.Float32()*2 - 1
	}
	return vector
}

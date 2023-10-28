package main

import (
	"context"
	"fmt"
	"log"
	"math/rand"
	"os"
	"sort"
	"strconv"
	"time"

	client "github.com/weaviate/weaviate-go-client/v4/weaviate"
	"github.com/weaviate/weaviate-go-client/v4/weaviate/graphql"
	"github.com/weaviate/weaviate/entities/models"
	"golang.org/x/sync/errgroup"
)

var (
	className  string
	dimensions int
	host       string
)

func init() {
	className = os.Getenv("CLASS_NAME")
	host = os.Getenv("HOST")
	var err error
	dimensions, err = strconv.Atoi(os.Getenv("DIMENSIONS"))
	if err != nil {
		panic(err)
	}
}

func do(ctx context.Context) error {
	config := client.Config{
		Scheme: "http",
		Host:   host,
	}
	c, err := client.NewClient(config)
	if err != nil {
		return err
	}

	tenants, err := getTenants(ctx, c)
	if err != nil {
		return err
	}

	if len(tenants) == 0 {
		return fmt.Errorf("no tenants found for class %q", className)
	}

	for iteration := 0; iteration < 1; iteration++ {
		if err := query(ctx, c, tenants); err != nil {
			return err
		}
	}

	return nil
}

var concurrencyIntervals = []int{1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30, 40, 50}

func query(ctx context.Context, client *client.Client,
	tenants []models.Tenant,
) error {
	log.Printf("start test 1, querying the same tenant concurrently")
	tenant := pickTenants(1, tenants)[0]
	for _, concurrency := range concurrencyIntervals {
		if err := querySingleTenant(ctx, client, tenant, concurrency); err != nil {
			return err
		}
	}

	log.Printf("start test 2, querying different tenants concurrently")
	for _, concurrency := range concurrencyIntervals {
		if err := queryManyTenants(ctx, client, concurrency, tenants); err != nil {
			return err
		}
	}

	return nil
}

func querySingleTenant(ctx context.Context, client *client.Client,
	tenant models.Tenant, concurrency int,
) error {
	eg := errgroup.Group{}
	durations := make([]time.Duration, concurrency) // Store query durations

	for i := 0; i < concurrency; i++ {
		startTime := time.Now() // Record the start time for the query

		i := i
		eg.Go(func() error {
			res, err := client.GraphQL().Get().WithClassName(className).
				WithFields(graphql.Field{Name: "_additional { id }"}).
				WithTenant(tenant.Name).
				WithLimit(10).
				WithNearVector(
					client.GraphQL().NearVectorArgBuilder().WithVector(randomVector()),
				).Do(ctx)

			endTime := time.Now()                   // Record the end time for the query
			queryDuration := endTime.Sub(startTime) // Calculate the query duration
			durations[i] = queryDuration            // Store the query duration

			if err != nil {
				return err
			}

			if len(res.Errors) > 0 {
				return fmt.Errorf("%v", res.Errors[0])
			}

			return nil
		})
	}

	if err := eg.Wait(); err != nil {
		return err
	}

	logTimes(concurrency, durations)

	return nil
}

func queryManyTenants(ctx context.Context, client *client.Client,
	concurrency int, allTenants []models.Tenant,
) error {
	eg := errgroup.Group{}
	durations := make([]time.Duration, concurrency) // Store query durations
	tenants := pickTenants(concurrency, allTenants)

	for i := 0; i < concurrency; i++ {
		startTime := time.Now() // Record the start time for the query

		i := i
		tenant := tenants[i]
		eg.Go(func() error {
			res, err := client.GraphQL().Get().WithClassName(className).
				WithFields(graphql.Field{Name: "_additional { id }"}).
				WithTenant(tenant.Name).
				WithLimit(10).
				WithNearVector(
					client.GraphQL().NearVectorArgBuilder().WithVector(randomVector()),
				).Do(ctx)

			endTime := time.Now()                   // Record the end time for the query
			queryDuration := endTime.Sub(startTime) // Calculate the query duration
			durations[i] = queryDuration            // Store the query duration

			if err != nil {
				return err
			}

			if len(res.Errors) > 0 {
				return fmt.Errorf("%v", res.Errors[0])
			}

			return nil
		})
	}

	if err := eg.Wait(); err != nil {
		return err
	}

	logTimes(concurrency, durations)

	return nil
}

func logTimes(concurrency int, durations []time.Duration) {
	// Calculate the mean and p99 of query durations
	var totalDuration time.Duration
	for _, duration := range durations {
		totalDuration += duration
	}

	meanDuration := totalDuration / time.Duration(concurrency)

	sort.Slice(durations, func(i, j int) bool {
		return durations[i] < durations[j]
	})

	p99Index := int(0.99 * float64(concurrency))
	p99Duration := durations[p99Index]

	// Print the mean and p99 query durations
	log.Printf("Concurrency=%d mean=%v, p99=%v", concurrency, meanDuration, p99Duration)
}

// func querySingleTenant(ctx context.Context, client *client.Client,
// 	tenant models.Tenant, concurrency int,
// ) error {
// 	eg := errgroup.Group{}
// 	for i := 0; i < concurrency; i++ {
// 		eg.Go(func() error {
// 			res, err := client.GraphQL().Get().WithClassName(className).
// 				WithFields(graphql.Field{Name: "_additional { id }"}).
// 				WithTenant(tenant.Name).
// 				WithLimit(10).
// 				WithNearVector(
// 					client.GraphQL().NearVectorArgBuilder().WithVector(randomVector()),
// 				).Do(ctx)
// 			if err != nil {
// 				return err
// 			}

// 			if len(res.Errors) > 0 {
// 				return fmt.Errorf("%v", res.Errors[0])
// 			}

// 			return nil
// 		})
// 	}

// 	return eg.Wait()
// }

func randomVector() []float32 {
	out := make([]float32, dimensions)
	for i := range out {
		out[i] = rand.Float32()
	}

	return out
}

func getTenants(ctx context.Context, client *client.Client) ([]models.Tenant, error) {
	before := time.Now()

	t, err := client.Schema().TenantsGetter().WithClassName(className).Do(ctx)
	if err != nil {
		return t, err
	}

	log.Printf("retrieved list of %d tenants in %s", len(t), time.Since(before))
	return t, nil
}

func main() {
	if err := do(context.Background()); err != nil {
		log.Fatal(err)
	}
}

func pickTenants(n int, tenants []models.Tenant) []models.Tenant {
	if n > len(tenants) {
		n = len(tenants) // Cap the number of picked tenants to the length of the slice.
	}

	// Create a copy of the original slice to avoid modifying the input slice.
	// We'll shuffle the copy to maintain the original order.
	shuffledTenants := make([]models.Tenant, len(tenants))
	copy(shuffledTenants, tenants)

	// Fisher-Yates shuffle
	for i := len(shuffledTenants) - 1; i > 0; i-- {
		j := rand.Intn(i + 1)
		shuffledTenants[i], shuffledTenants[j] = shuffledTenants[j], shuffledTenants[i]
	}

	// Return the first n shuffled tenants.
	return shuffledTenants[:n]
}

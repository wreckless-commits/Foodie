using Foodie.Api;
using Npgsql;
using OpenTelemetry.Logs;
using OpenTelemetry.Metrics;
using OpenTelemetry.Trace;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenApi();

builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter())
    .WithMetrics(metrics => metrics
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddMeter("Microsoft.AspNetCore.Hosting")
        .AddMeter("Microsoft.AspNetCore.Server.Kestrel")
        .AddOtlpExporter());

builder.Logging.AddOpenTelemetry(options =>
{
    options.IncludeFormattedMessage = true;
    options.IncludeScopes = true;
    options.AddOtlpExporter();
});

builder.AddNpgsqlDataSource("foodiedb", static settings =>
{
    if (settings.ConnectionString is { } cs)
    {
        var builder = new NpgsqlConnectionStringBuilder(cs)
        {
            Pooling = true,
            MaxPoolSize = 20,
            ConnectionIdleLifetime = 300,
            ConnectionPruningInterval = 10
        };
        settings.ConnectionString = builder.ConnectionString;
    }
});

builder.Services.AddHttpClient("ollama", client => { client.BaseAddress = new Uri("http://localhost:11434"); });

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

using (var scope = app.Services.CreateScope())
{
    var ds = scope.ServiceProvider.GetRequiredService<NpgsqlDataSource>();
    await using var conn = await ds.OpenConnectionAsync();

    // Create items table if non-existent
    await using var schemaCmd = conn.CreateCommand();
    schemaCmd.CommandText = """
                            -- Enable PG Vector
                            CREATE EXTENSION IF NOT EXISTS vector;
                            -- Create Table
                            CREATE TABLE IF NOT EXISTS items (
                                id          SERIAL PRIMARY KEY,
                                original_id INTEGER UNIQUE NOT NULL,
                                recipe_text TEXT NOT NULL,
                                embedding   VECTOR(768)
                            );
                            """;
    await schemaCmd.ExecuteNonQueryAsync();

    if (app.Configuration.GetValue<bool>("VectorIndex:Enabled"))
    {
        // Construct HNSW index, note ef_construction value
        await using var indexCmd = conn.CreateCommand();
        indexCmd.CommandText = """
                               CREATE INDEX IF NOT EXISTS idx_items_embedding
                                   ON items USING hnsw (embedding vector_cosine_ops)
                                   -- [m] is the total connections to other nodes in the graph
                                   -- [ef_construction] allows for better understanding of neighbouring nodes
                                   -- only will slow down index build but provides better quality during recall
                                   WITH (m = 16, ef_construction = 200);
                               """;
        indexCmd.CommandTimeout = 300;
        await indexCmd.ExecuteNonQueryAsync();
    }
}

app.UseHttpsRedirection();
app.MapSemanticSearchEndPoints();

app.Run();
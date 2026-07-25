using System.Diagnostics;
using System.Globalization;
using Microsoft.AspNetCore.Mvc;
using Npgsql;

namespace Foodie.Api;

public static class SemanticSearchEndpoint
{
    public static void MapSemanticSearchEndPoints(this WebApplication app)
    {
        app.MapGet("/api/search", Search);
    }

    private static async Task<List<RecipeHit>> Search([FromQuery] string query, [FromQuery] int topK,
        [FromQuery] bool exact = false,
        IHttpClientFactory httpFactory = default!,
        NpgsqlDataSource ds = default!,
        ILoggerFactory loggerFactory = default!
    )
    {
        var logger = loggerFactory.CreateLogger("Foodie.Api.Search");
        var start = Stopwatch.GetTimestamp();

        logger.LogInformation("Searching for recipes: {Query}, topK: {TopK}, exact: {Exact}", query, topK, exact);

        var http = httpFactory.CreateClient("ollama");
        var queryVector = await EmbedQueryAsync(http, query);

        await using var connection = await ds.OpenConnectionAsync();
        await using var transaction = connection.BeginTransaction();

        if (exact)
        {
            await using var setCmd = connection.CreateCommand();
            setCmd.CommandText = "SET LOCAL enable_indexscan = OFF";
            await setCmd.ExecuteNonQueryAsync();
        }
        else
        {
            await using var setCmd = connection.CreateCommand();
            setCmd.CommandText = "SET LOCAL hnsw.ef_search = 100;";
            await setCmd.ExecuteNonQueryAsync();
        }

        await using var command = new NpgsqlCommand(@"
            SELECT id, original_id, recipe_text,
                   embedding <=> $1::vector(768) as distance
            FROM items
            ORDER BY distance
            LIMIT $2", connection);

        var vectorStr = "[" + string.Join(",", queryVector.ConvertAll(f => f.ToString(CultureInfo.InvariantCulture))) + "]";
        command.Parameters.Add(new NpgsqlParameter { Value = vectorStr });
        command.Parameters.Add(new NpgsqlParameter { Value = topK });

        var results = new List<RecipeHit>();
        {
            await using var reader = await command.ExecuteReaderAsync();
            while (await reader.ReadAsync())
            {
                results.Add(new RecipeHit(
                    reader.GetInt32(0),
                    reader.GetInt32(1),
                    reader.GetString(2),
                    reader.GetDouble(3)
                ));
            }
        }

        await transaction.CommitAsync();

        var elapsed = Stopwatch.GetElapsedTime(start);
        logger.LogInformation("Found {Count} results for query: {Query} in {ElapsedMs}ms",
            results.Count, query, elapsed.TotalMilliseconds);

        return results;
    }

    private static async Task<List<float>> EmbedQueryAsync(HttpClient httpClient, string query)
    {
        var response = await httpClient.PostAsJsonAsync("/api/embed", new
        {
            model = "nomic-embed-text",
            input = new[] { query }
        });

        var json = await response.Content.ReadFromJsonAsync<OllamaResponse>();

        return json.Embeddings[0];
    }

    record RecipeHit(int Id, int OriginalId, string RecipeText, double Distance);

    record OllamaResponse(List<List<float>> Embeddings);
}
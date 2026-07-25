var builder = DistributedApplication.CreateBuilder(args);
var dbPassword = builder.AddParameter("DBPASSWORD", builder.Configuration.GetSection("ConnectionStrings")["DB_PASSWORD"]);

// PGSQL server and persistent store, lets not lose our 2M rows on restart :)
var postgres = builder.AddPostgres("postgres",password: dbPassword,port:5430)
    .WithLifetime(ContainerLifetime.Persistent)
    .WithDataVolume(name: "foodie-pgdata")
    .WithImage("pgvector/pgvector", "pg17");// Uses image with pgvector pre-installed

var database = postgres.AddDatabase("foodiedb");

// API server
var webApi = builder.AddProject<Projects.Foodie_Api>("api")
    .WaitFor(database)
    .WithReference(database,connectionName:"foodiedb")
    .WithExternalHttpEndpoints();

// Web UI
builder.AddPythonApp(
    name: "foodie-search",
    scriptPath: "foodie-search.py",
    appDirectory: "../streamlit"
    )
    .WaitFor(webApi)
    .WithHttpEndpoint(port:8000, env:"PORT");

builder.Build().Run();
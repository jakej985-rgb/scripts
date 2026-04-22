# Infernal Ink Tattoo Web App: Docker Setup Guide

This guide explains how to compile and deploy the **Infernal Ink Tattoo Web App** (API Backend & Frontend) into the M3TAL Media Server's Docker environment.

## 1. Prerequisites: Environment Variables

Before deploying the Tattoo App, ensure your M3TAL `.env` file (located at the root of the repository) is configured with the necessary environment variables.

Specifically, verify the following are set:
- `REPO_ROOT`: The absolute path to your `M3tal-Media-Server` repository.
- `DATA_DIR`: The absolute path where you want Docker volumes (databases, uploads) to reside.
- `DOMAIN`: Your Traefik domain (e.g., `m3tal-media-server.xyz`) which will host the app at `tattoo.m3tal-media-server.xyz`.
- `TATTOO_DB_PASSWORD`: Even if you are utilizing the default SQLite database, this is kept for the legacy Postgres container.
- `DASHBOARD_SECRET`: Used for cryptographic operations across the suite.

## 2. Compile and Publish the .NET Applications

The Docker setup relies on local published versions of the .NET applications. The containers mount these published directories so that any updates to the C# code can be applied by simply re-publishing the project without rebuilding the Docker images.

You need to publish BOTH the API backend and the Web frontend.

Run the following commands from the repository root:

```powershell
# 1. Publish the API (Backend)
cd Infernal-Ink-Steel-Suite\InfernalInkSteelSuite.Api
dotnet publish -c Release -o publish

# 2. Publish the Web App (Frontend)
cd ..\InfernalInkSteelSuite.Web
dotnet publish -c Release -o publish
```

This creates the necessary DLLs in their respective `publish` folders.

## 3. Review the Docker Compose Configuration

The stack is defined in `docker\apps\tattoo-app\docker-compose.yml` and utilizes a two-container architecture for the application, plus a database container.

- **API Container (`tattoo-api`)**: Runs the ASP.NET Core API Backend (`InfernalInkSteelSuite.Api.dll`) on port 5000 internally. It mounts your `DATA_DIR` to save SQLite database files (`/data/tattoo.db`) and user uploads (`/app/wwwroot/uploads`).
- **Web Container (`tattoo-web`)**: Runs the ASP.NET Core Frontend (`InfernalInkSteelSuite.Web.dll`). It communicates with the API via the `ApiBaseUrl` environment variable (`http://tattoo-api:5000`). Traefik routes public traffic to this container.
- **Database Container (`tattoo-db`)**: A Postgres container provided for future migration or legacy compatibility. 

*Note: The Infernal Ink API currently defaults to Entity Framework Core with SQLite. The SQLite `.db` file will automatically be created in your `DATA_DIR/tattoo/db` directory on the first run.*

## 4. Start the Application

You can start the web app by deploying its Docker Compose stack. Since M3TAL manages network routing through Traefik, ensure the `routing` stack is up first.

Navigate to the compose file and bring the stack up:

```powershell
cd docker\apps\tattoo-app

# Start the stack (use the M3TAL global .env file)
docker compose --env-file ../../../.env up -d
```

### Alternatively: Using the M3TAL Control Plane
If you want to allow the M3TAL Autonomous Agents to adopt the stack:
Simply ensure the `m3tal.stack=tattoo-app` label is present (which it is), and the `registry` agent will automatically detect and monitor it on its next 60-second tick.

## 5. Verify the Deployment

1. Check the logs to ensure the EF Core migrations applied successfully and the app is listening:
   ```powershell
   docker logs tattoo-api
   ```
2. Navigate to your defined domain: `https://tattoo.your-domain.xyz`
3. **Default Credentials**: If this is a fresh database in a `Development` environment, the API automatically seeds two accounts:
   - Admin: `admin` / `admin123`
   - Artist: `artist1` / `artist123`
   
   *(Ensure you change these immediately upon moving to production!)*

## Troubleshooting

- **ENOENT or Missing DLL**: If Docker crashes saying it can't find `InfernalInkSteelSuite.Api.dll`, ensure you ran the `dotnet publish` command in Step 2.
- **SQLite Lock Errors**: Ensure your `DATA_DIR/tattoo/db` directory has the correct write permissions for the Docker container user (`PUID/PGID` defined in your `.env`).
- **Traefik 404/502**: Ensure the `proxy` network exists and that your `DOMAIN` variable is set correctly in `.env`.

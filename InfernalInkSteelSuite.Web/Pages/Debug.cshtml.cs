using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.Data.Sqlite;
using System.Diagnostics;
using System.Security.Principal;

namespace InfernalInkSteelSuite.Web.Pages
{
    [Microsoft.AspNetCore.Authorization.AllowAnonymous]
    public class DebugModel(IConfiguration configuration, IWebHostEnvironment env) : PageModel
    {
        private readonly IConfiguration _configuration = configuration;
        private readonly IWebHostEnvironment _env = env;

        public string ContentRootPath { get; set; } = "";
        public string WebRootPath { get; set; } = "";
        public string ProcessName { get; set; } = "";
        public string UserName { get; set; } = "";
        public string ConnectionStringConfig { get; set; } = "";
        public string DbPath { get; set; } = "";
        public bool DirExists { get; set; }
        public bool FileExists { get; set; }
        public string FileAttributes { get; set; } = "";
        public bool CanRead { get; set; }
        public bool CanWrite { get; set; }
        public string ConnectionResult { get; set; } = "";
        public string ConnectionError { get; set; } = "";

        public void OnGet()
        {
            ContentRootPath = _env.ContentRootPath;
            WebRootPath = _env.WebRootPath;
            ProcessName = Process.GetCurrentProcess().ProcessName;
            if (OperatingSystem.IsWindows())
            {
                UserName = WindowsIdentity.GetCurrent().Name;
            }
            else
            {
                UserName = "Non-Windows Environment";
            }

            ConnectionStringConfig = _configuration.GetConnectionString("DefaultConnection") ?? "Not Found";

            if (ConnectionStringConfig.Contains("Data Source="))
            {
                DbPath = ConnectionStringConfig.Replace("Data Source=", "").Trim();
            }
            else
            {
                DbPath = "Could not parse path";
            }

            if (!string.IsNullOrEmpty(DbPath) && DbPath != "Could not parse path")
            {
                var dir = Path.GetDirectoryName(DbPath);
                DirExists = Directory.Exists(dir);
                FileExists = System.IO.File.Exists(DbPath);

                if (FileExists)
                {
                    try
                    {
                        var info = new FileInfo(DbPath);
                        FileAttributes = info.Attributes.ToString();
                    }
                    catch (Exception ex) { FileAttributes = "Error: " + ex.Message; }

                    try
                    {
                        using var fs = System.IO.File.OpenRead(DbPath);
                        CanRead = true;
                    }
                    catch { CanRead = false; }

                    try
                    {
                        using var fs = System.IO.File.OpenWrite(DbPath);
                        CanWrite = true;
                    }
                    catch { CanWrite = false; }
                }
            }

            try
            {
                using var conn = new SqliteConnection(ConnectionStringConfig);
                conn.Open();
                ConnectionResult = "Success! State: " + conn.State;

                using var cmd = conn.CreateCommand();
                cmd.CommandText = "SELECT sqlite_version()";
                var version = cmd.ExecuteScalar()?.ToString();
                ConnectionResult += $" (SQLite Version: {version})";
            }
            catch (Exception ex)
            {
                ConnectionResult = "Failed";
                ConnectionError = ex.ToString();
            }
        }
    }
}

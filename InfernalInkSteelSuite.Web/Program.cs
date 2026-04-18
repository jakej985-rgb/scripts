using InfernalInkSteelSuite.Web.Services;
using InfernalInkSteelSuite.Data;
using InfernalInkSteelSuite.Repositories;

var builder = WebApplication.CreateBuilder(args);

builder.Configuration
    .AddJsonFile("appsettings.json", optional: false, reloadOnChange: true)
    .AddJsonFile($"appsettings.{builder.Environment.EnvironmentName}.json", optional: true)
    .AddEnvironmentVariables();

// Razor Pages
builder.Services.AddRazorPages();
builder.Services.AddControllersWithViews(); // Add MVC support

builder.Services.AddHttpContextAccessor();

// Sessions to track logged-in user
builder.Services.AddSession(options =>
{
    options.IdleTimeout = TimeSpan.FromHours(8);
});

// Configure ApiOptions
builder.Services.Configure<ApiOptions>(builder.Configuration);

// HttpClient for API
builder.Services.AddHttpClient<ApiClient>();

// Database & Repositories
var connectionString = builder.Configuration.GetConnectionString("DefaultConnection");
if (string.IsNullOrEmpty(connectionString))
{
    throw new InvalidOperationException("Connection string 'DefaultConnection' not found.");
}

// Ensure database directory exists
var dbPath = connectionString.Replace("Data Source=", "");
var dbDir = Path.GetDirectoryName(dbPath);
if (!string.IsNullOrEmpty(dbDir) && !Directory.Exists(dbDir))
{
    Directory.CreateDirectory(dbDir);
}

// Ensure database is initialized
// var dbManager = new DatabaseManager(connectionString);
// dbManager.InitializeDatabase();

builder.Services.AddScoped<IUserRepository>(sp => new UserRepository(connectionString));
builder.Services.AddScoped<IClientRepository>(sp => new ClientRepository(connectionString));
builder.Services.AddScoped<IAppointmentRepository>(sp => new AppointmentRepository(connectionString));
builder.Services.AddScoped<IDocumentRepository>(sp => new DocumentRepository(connectionString));
builder.Services.AddScoped<IShopSettingsRepository>(sp => new ShopSettingsRepository(connectionString));


var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();

app.UseRouting();

app.UseSession();

app.UseAuthorization();

// 👇 add this line BEFORE MapRazorPages
app.MapGet("/", () => Results.Redirect("/Account/Login"));

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Home}/{action=Index}/{id?}");

app.MapRazorPages();
app.MapControllers();

app.Run();

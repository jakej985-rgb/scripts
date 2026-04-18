using InfernalInkSteelSuite.Web.Models;
using Microsoft.AspNetCore.Http;
using Microsoft.Extensions.Options;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Net.Http.Json;

namespace InfernalInkSteelSuite.Web.Services;

public class ApiOptions
{
    public string ApiBaseUrl { get; set; } = "";
}

public class ApiClient
{
    private readonly HttpClient _http;
    private readonly IHttpContextAccessor _httpContextAccessor;
    private readonly ApiOptions _options;

    public ApiClient(HttpClient http, IOptions<ApiOptions> options, IHttpContextAccessor httpContextAccessor)
    {
        _http = http;
        _httpContextAccessor = httpContextAccessor;
        _options = options.Value;

        if (!string.IsNullOrWhiteSpace(_options.ApiBaseUrl))
        {
            _http.BaseAddress = new Uri(_options.ApiBaseUrl);
        }
    }

    private void ApplyAuthHeader()
    {
        var httpContext = _httpContextAccessor.HttpContext;
        if (httpContext == null)
        {
            _http.DefaultRequestHeaders.Authorization = null;
            return;
        }

        var token = httpContext.Session.GetString("ApiToken");

        if (!string.IsNullOrWhiteSpace(token))
        {
            _http.DefaultRequestHeaders.Authorization =
                new AuthenticationHeaderValue("Bearer", token);
        }
        else
        {
            _http.DefaultRequestHeaders.Authorization = null;
        }
    }

    // DTOs matching the API responses
    public record LoginRequest(string Username, string Password);
    public record LoginResponse(int UserId, string Username, string DisplayName, string Role, string Token);

    public record DocumentDto(
        int Id,
        int ClientId,
        int UploadedByUserId,
        string Title,
        string FilePath,
        DateTime CreatedAt
    );

    // Stats DTOs
    public record DashboardStatsDto(int AppointmentsToday, int TotalClients, List<ClientSummaryDto> RecentClients, bool IsShopOpen, int ActiveArtistsCount, int UpcomingAppointments, int OpenQuotes);
    public record ClientSummaryDto(int Id, string Name, string Email);
    public record AppointmentStatDto(DateTime Date, int Count);

    // Quote DTOs
    public class QuoteInput
    {
        public int? ClientId { get; set; }
        public string Placement { get; set; } = string.Empty;
        public string Style { get; set; } = string.Empty;
        public bool IsCoverUp { get; set; }
        public double Width { get; set; }
        public double Height { get; set; }
        public int CoverageLevel { get; set; }
        public int LineComplexity { get; set; }
        public int ShadingComplexity { get; set; }
        public int ColorComplexity { get; set; }
        public int Difficulty { get; set; }
        public int ArtistId { get; set; }
        public string? Notes { get; set; }
        public string? PhotoPath { get; set; }
    }

    public class QuoteEstimate
    {
        public double EstimatedHoursLow { get; set; }
        public double EstimatedHoursHigh { get; set; }
        public decimal PriceLow { get; set; }
        public decimal PriceHigh { get; set; }
        public decimal ShopMinimum { get; set; }
        public decimal RecommendedDeposit { get; set; }
        public double ConfidenceScore { get; set; }
        public int SimilarJobsCount { get; set; }
    }

    public class QuoteDto : QuoteEstimate
    {
        public int Id { get; set; }
        public int? ClientId { get; set; }
        public int ArtistId { get; set; }
        public string Placement { get; set; } = string.Empty;
        public string Style { get; set; } = string.Empty;
        public bool IsCoverUp { get; set; }
        public double Width { get; set; }
        public double Height { get; set; }
        public int CoverageLevel { get; set; }
        public int LineComplexity { get; set; }
        public int ShadingComplexity { get; set; }
        public int ColorComplexity { get; set; }
        public int Difficulty { get; set; }
        public string? Notes { get; set; }
        public string? PhotoPath { get; set; }
        public DateTime CreatedAt { get; set; }
    }


    public async Task<LoginResponse?> LoginAsync(string username, string password)
    {
        var resp = await _http.PostAsJsonAsync("/auth/login", new LoginRequest(username, password));
        if (!resp.IsSuccessStatusCode) return null;

        return await resp.Content.ReadFromJsonAsync<LoginResponse>();
    }

    public async Task<List<ClientDto>> GetClientsAsync()
    {
        ApplyAuthHeader();
        var result = await _http.GetFromJsonAsync<List<ClientDto>>("api/clients");
        return result ?? [];
    }

    public async Task<ClientDto?> GetClientAsync(int id)
    {
        ApplyAuthHeader();
        return await _http.GetFromJsonAsync<ClientDto>($"api/clients/{id}");
    }

    public async Task<ClientDto> CreateClientAsync(ClientDto client)
    {
        ApplyAuthHeader();
        var response = await _http.PostAsJsonAsync("api/clients", client);
        if (!response.IsSuccessStatusCode)
        {
            var error = await response.Content.ReadAsStringAsync();
            throw new ApiException(response.StatusCode, string.IsNullOrWhiteSpace(error) ? "Failed to create client." : error);
        }
        return await response.Content.ReadFromJsonAsync<ClientDto>() ?? throw new InvalidOperationException("API returned null.");
    }

    public async Task UpdateClientAsync(ClientDto client)
    {
        ApplyAuthHeader();
        var response = await _http.PutAsJsonAsync($"api/clients/{client.Id}", client);
        if (!response.IsSuccessStatusCode)
        {
            var error = await response.Content.ReadAsStringAsync();
            throw new ApiException(response.StatusCode, string.IsNullOrWhiteSpace(error) ? "Failed to update client." : error);
        }
    }

    public async Task<List<AppointmentDto>> GetAppointmentsAsync(DateTime? date = null, int? artistId = null, string? status = null, int? clientId = null)
    {
        ApplyAuthHeader();
        var query = new List<string>();
        if (date.HasValue) query.Add($"date={date.Value:O}");
        if (artistId.HasValue) query.Add($"artistId={artistId.Value}");
        if (clientId.HasValue) query.Add($"clientId={clientId.Value}");
        if (!string.IsNullOrWhiteSpace(status)) query.Add($"status={status}");
        var qs = query.Count > 0 ? "?" + string.Join("&", query) : string.Empty;

        var result = await _http.GetFromJsonAsync<List<AppointmentDto>>($"api/appointments{qs}");
        return result ?? [];
    }

    public async Task<AppointmentDto?> GetAppointmentAsync(int id)
    {
        ApplyAuthHeader();
        return await _http.GetFromJsonAsync<AppointmentDto>($"api/appointments/{id}");
    }

    public async Task<AppointmentDto> CreateAppointmentAsync(AppointmentDto appt)
    {
        ApplyAuthHeader();
        var response = await _http.PostAsJsonAsync("api/appointments", appt);
        if (!response.IsSuccessStatusCode)
        {
            var error = await response.Content.ReadAsStringAsync();
            throw new ApiException(response.StatusCode, string.IsNullOrWhiteSpace(error) ? "Failed to create appointment." : error);
        }
        return await response.Content.ReadFromJsonAsync<AppointmentDto>() ?? throw new InvalidOperationException("API returned null.");
    }

    public async Task UpdateAppointmentAsync(AppointmentDto appt)
    {
        ApplyAuthHeader();
        var response = await _http.PutAsJsonAsync($"api/appointments/{appt.Id}", appt);
        if (!response.IsSuccessStatusCode)
        {
            var error = await response.Content.ReadAsStringAsync();
            throw new ApiException(response.StatusCode, string.IsNullOrWhiteSpace(error) ? "Failed to update appointment." : error);
        }
    }

    // DOCUMENTS

    public Task<List<DocumentDto>?> GetDocumentsAsync()
    {
        ApplyAuthHeader();
        return _http.GetFromJsonAsync<List<DocumentDto>>("api/Documents");
    }

    public async Task<List<DocumentDto>> GetDocumentsForClientAsync(int clientId)
    {
        ApplyAuthHeader();
        // Updated endpoint to match new controller if needed, but the new controller exposes "api/Documents/by-client/{clientId}"
        var result = await _http.GetFromJsonAsync<List<DocumentDto>>($"api/Documents/by-client/{clientId}");
        return result ?? [];
    }

    public async Task<List<UserDto>> GetUsersAsync()
    {
        ApplyAuthHeader();
        var result = await _http.GetFromJsonAsync<List<UserDto>>("api/Users");
        return result ?? [];
    }

    public async Task<DocumentDto?> UploadDocumentAsync(
        int clientId,
        int uploadedByUserId,
        string? title,
        IFormFile file)
    {
        ApplyAuthHeader();
        using var content = new MultipartFormDataContent
        {
            { new StringContent(clientId.ToString()), "clientId" },
            { new StringContent(uploadedByUserId.ToString()), "uploadedByUserId" }
        };

        if (!string.IsNullOrWhiteSpace(title))
            content.Add(new StringContent(title), "title");

        await using var stream = file.OpenReadStream();
        var streamContent = new StreamContent(stream);
        content.Add(streamContent, "file", file.FileName);

        var response = await _http.PostAsync("api/Documents", content);
        if (!response.IsSuccessStatusCode)
            return null;

        return await response.Content.ReadFromJsonAsync<DocumentDto>();
    }

    public async Task<string?> UploadAvatarAsync(int clientId, Stream imageStream, string fileName)
    {
        ApplyAuthHeader();
        using var content = new MultipartFormDataContent();
        var streamContent = new StreamContent(imageStream);
        // Assuming JPEG from smartcrop or detect via filename
        streamContent.Headers.ContentType = new MediaTypeHeaderValue("image/jpeg");
        content.Add(streamContent, "file", fileName);

        var response = await _http.PostAsync($"api/clients/{clientId}/avatar", content);
        if (!response.IsSuccessStatusCode) return null;

        try
        {
            var result = await response.Content.ReadFromJsonAsync<System.Text.Json.JsonElement>();
            if (result.TryGetProperty("photoPath", out var prop)) return prop.GetString();
            if (result.TryGetProperty("PhotoPath", out prop)) return prop.GetString();
        }
        catch { } // Fallback

        return null;
    }

    // QUOTES

    public async Task<QuoteEstimate?> CalculateQuoteAsync(QuoteInput input)
    {
        ApplyAuthHeader();
        var response = await _http.PostAsJsonAsync("api/Quotes/preview", input);
        if (!response.IsSuccessStatusCode) return null;
        return await response.Content.ReadFromJsonAsync<QuoteEstimate>();
    }

    public async Task<QuoteDto?> CreateQuoteAsync(QuoteInput input)
    {
        ApplyAuthHeader();
        var response = await _http.PostAsJsonAsync("api/Quotes", input);
        if (!response.IsSuccessStatusCode) return null;
        return await response.Content.ReadFromJsonAsync<QuoteDto>();
    }

    public async Task<List<QuoteDto>> GetAllQuotesAsync()
    {
        ApplyAuthHeader();
        var result = await _http.GetFromJsonAsync<List<QuoteDto>>("api/Quotes");
        return result ?? [];
    }

    // STATS

    public async Task<DashboardStatsDto?> GetDashboardStatsAsync()
    {
        ApplyAuthHeader();
        try
        {
            return await _http.GetFromJsonAsync<DashboardStatsDto>("api/Stats/overview");
        }
        catch (HttpRequestException)
        {
            // Fallback if API down or empty
            return new DashboardStatsDto(0, 0, [], false, 0, 0, 0);
        }
    }

    public async Task<List<AppointmentStatDto>> GetAppointmentStatsAsync(DateTime? from, DateTime? to)
    {
        ApplyAuthHeader();
        var query = new List<string>();
        if (from.HasValue) query.Add($"from={from.Value:O}");
        if (to.HasValue) query.Add($"to={to.Value:O}");
        var qs = query.Count > 0 ? "?" + string.Join("&", query) : string.Empty;

        var result = await _http.GetFromJsonAsync<List<AppointmentStatDto>>($"api/Stats/appointments-by-day{qs}");
        return result ?? [];
    }

    // SETTINGS

    public class ShopSettingsDto
    {
        public string ShopName { get; set; } = string.Empty;
        public string LogoPath { get; set; } = string.Empty;
        public string AccentColor { get; set; } = string.Empty;
        public string SidebarArtworkPath { get; set; } = string.Empty;
        public string LoginBackgroundPath { get; set; } = string.Empty;
        public string LoginHeadlineFontFamily { get; set; } = string.Empty;
        public string LoginTaglineFontFamily { get; set; } = string.Empty;
        public string LoginTextColor { get; set; } = string.Empty;

        // Rates
        public double TattooPerHour { get; set; }
        public double PiercingSingle { get; set; }
        public double PiercingMulti { get; set; }
        public double ShopMinimumRate { get; set; }
        public double TaxRate { get; set; }

        // Deposits & Booking
        public string DepositType { get; set; } = "Percentage";
        public double DepositAmount { get; set; }
        public int BookingBufferMinutes { get; set; }
        public string CancellationPolicy { get; set; } = string.Empty;

        // Features / Toggles
        public bool EnableAutomaticHolidayThemes { get; set; }
        public bool IsSpecialMessageEnabled { get; set; }
        public string SpecialMessageText { get; set; } = string.Empty;
        public double AppFontSize { get; set; } = 14.0;

        // JSON Blobs
        public string ShopHoursJson { get; set; } = string.Empty;
        public string SpecialHoursJson { get; set; } = string.Empty;
        public string AppointmentDurationPresetsJson { get; set; } = string.Empty;
        public string NotificationSettingsJson { get; set; } = string.Empty;
        public string BackupSettingsJson { get; set; } = string.Empty;
        public string LinkedAccountsJson { get; set; } = string.Empty;

        // Legacy / Transient
        public string Theme { get; set; } = "Neon"; // Used for Web Theme selection
    }

    public async Task<ShopSettingsDto?> GetShopSettingsAsync()
    {
        ApplyAuthHeader();
        try
        {
            return await _http.GetFromJsonAsync<ShopSettingsDto>("api/Settings");
        }
        catch (HttpRequestException)
        {
            return null;
        }
    }

    public class PublicShopSettingsDto
    {
        public string ShopName { get; set; } = "Infernal Ink";
        public string LogoPath { get; set; } = string.Empty;
        public string LoginBackgroundPath { get; set; } = string.Empty;
        public bool IsSpecialMessageEnabled { get; set; }
        public string SpecialMessageText { get; set; } = string.Empty;
        public string LoginHeadlineFontFamily { get; set; } = string.Empty;
        public string LoginTaglineFontFamily { get; set; } = string.Empty;
        public string LoginTextColor { get; set; } = string.Empty;
    }

    public async Task<PublicShopSettingsDto?> GetPublicShopSettingsAsync()
    {
        try
        {
            return await _http.GetFromJsonAsync<PublicShopSettingsDto>("api/Settings/public");
        }
        catch
        {
            return new PublicShopSettingsDto();
        }
    }

    public async Task<bool> UpdateShopSettingsAsync(ShopSettingsDto settings)
    {
        ApplyAuthHeader();
        var response = await _http.PutAsJsonAsync("api/Settings", settings);
        return response.IsSuccessStatusCode;
    }
}

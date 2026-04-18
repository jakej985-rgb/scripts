using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using System.Text.Json;
using InfernalInkSteelSuite.Domain;
using System.ComponentModel.DataAnnotations;

namespace InfernalInkSteelSuite.Web.Pages.Settings
{
    public class IndexModel(ApiClient api) : PageModel
    {
        private readonly ApiClient _api = api;

        [BindProperty]
        public ApiClient.ShopSettingsDto Settings { get; set; } = new();

        [BindProperty]
        public string SelectedTheme { get; set; } = "Neon";

        // --- Helper Models for JSON sections ---

        [BindProperty]
        public List<ShopDaySetting> ShopHours { get; set; } = [];

        [BindProperty]
        public NotificationSettingsModel NotificationSettings { get; set; } = new();

        [BindProperty]
        public BackupSettingsModel BackupSettings { get; set; } = new();

        [BindProperty]
        public LinkedAccountsModel LinkedAccounts { get; set; } = new();

        public List<UserDto> Users { get; set; } = [];
        public string CurrentUser_Username { get; set; } = string.Empty;

        public async Task<IActionResult> OnGetAsync()
        {
            var token = HttpContext.Session.GetString("ApiToken");
            if (string.IsNullOrEmpty(token)) return RedirectToPage("/Account/Login");

            var role = HttpContext.Session.GetString("Role");
            if (role != "Admin" && role != "Manager")
            {
                // Only Admin/Manager can view settings
                return RedirectToPage("/Index");
            }

            var settings = await _api.GetShopSettingsAsync();
            if (settings != null)
            {
                Settings = settings;
                SelectedTheme = Settings.Theme; // Load current theme (if persisted or default)

                // Deserialize JSON helpers
                LoadShopHours(Settings.ShopHoursJson);
                LoadNotificationSettings(Settings.NotificationSettingsJson);
                LoadBackupSettings(Settings.BackupSettingsJson);
                LoadBackupSettings(Settings.BackupSettingsJson);
                LoadLinkedAccounts(Settings.LinkedAccountsJson);
            }

            // Fetch Users for Staff Management
            Users = await _api.GetUsersAsync();
            CurrentUser_Username = HttpContext.Session.GetString("Username") ?? "Unknown";

            return Page();
        }

        public async Task<IActionResult> OnPostAsync()
        {
            var token = HttpContext.Session.GetString("ApiToken");
            if (string.IsNullOrEmpty(token)) return RedirectToPage("/Account/Login");

            // Serialize helpers back to JSON
            Settings.ShopHoursJson = JsonSerializer.Serialize(ShopHours);
            Settings.NotificationSettingsJson = JsonSerializer.Serialize(NotificationSettings);
            Settings.BackupSettingsJson = JsonSerializer.Serialize(BackupSettings);
            Settings.LinkedAccountsJson = JsonSerializer.Serialize(LinkedAccounts);

            // Theme handling
            Settings.Theme = SelectedTheme;

            var success = await _api.UpdateShopSettingsAsync(Settings);

            if (success)
                TempData["Message"] = "Settings saved successfully.";
            else
                TempData["Message"] = "Failed to save settings.";

            return Page();
        }

        private void LoadShopHours(string json)
        {
            if (string.IsNullOrEmpty(json))
            {
                // Default Hours
                ShopHours = Enum.GetValues<DayOfWeek>().Select(d => new ShopDaySetting
                {
                    Day = d,
                    IsOpen = d != DayOfWeek.Sunday,
                    StartTime = new TimeSpan(10, 0, 0),
                    EndTime = new TimeSpan(19, 0, 0)
                }).ToList();
            }
            else
            {
                try { ShopHours = JsonSerializer.Deserialize<List<ShopDaySetting>>(json) ?? []; }
                catch { ShopHours = []; }
            }
        }

        private void LoadNotificationSettings(string json)
        {
            if (!string.IsNullOrEmpty(json))
            {
                try { NotificationSettings = JsonSerializer.Deserialize<NotificationSettingsModel>(json) ?? new(); }
                catch { NotificationSettings = new(); }
            }
        }

        private void LoadBackupSettings(string json)
        {
            if (!string.IsNullOrEmpty(json))
            {
                try { BackupSettings = JsonSerializer.Deserialize<BackupSettingsModel>(json) ?? new(); }
                catch { BackupSettings = new(); }
            }
        }

        private void LoadLinkedAccounts(string json)
        {
            if (!string.IsNullOrEmpty(json))
            {
                try { LinkedAccounts = JsonSerializer.Deserialize<LinkedAccountsModel>(json) ?? new(); }
                catch { LinkedAccounts = new(); }
            }
        }

        public class NotificationSettingsModel
        {
            public bool EmailAppointmentReminders { get; set; } = true;
            public bool SmsAppointmentReminders { get; set; }
            public string ReminderTiming { get; set; } = "1 day before";
        }

        public class BackupSettingsModel
        {
            public string BackupPath { get; set; } = @"C:\Backups\InfernalInk";
            public bool AutoBackupEnabled { get; set; }
            public string BackupFrequency { get; set; } = "Daily";
            public int RetentionDays { get; set; } = 30;
        }

        public class LinkedAccountsModel
        {
            public string InstagramUrl { get; set; } = "";
            public string FacebookUrl { get; set; } = "";
            public string TwitterUrl { get; set; } = "";
            public string WebsiteUrl { get; set; } = "";
        }
    }
}

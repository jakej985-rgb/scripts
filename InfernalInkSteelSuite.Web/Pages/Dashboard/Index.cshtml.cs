using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using static InfernalInkSteelSuite.Web.Services.ApiClient;

namespace InfernalInkSteelSuite.Web.Pages.Dashboard;

public class IndexModel(ApiClient api) : PageModel
{
    private readonly ApiClient _api = api;

    public DashboardStatsDto? Stats { get; set; }
    public List<AppointmentDto> TodaysAppointments { get; set; } = [];

    public async Task<IActionResult> OnGetAsync()
    {
        // 1. Require login
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
        {
            return RedirectToPage("/Account/Login");
        }

        // 2. Load summary stats
        Stats = await _api.GetDashboardStatsAsync();

        // 3. Load today's appointments
        var today = DateTime.Today;
        TodaysAppointments = await _api.GetAppointmentsAsync(date: today);

        return Page();
    }
}

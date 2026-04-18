using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers;

public class StatisticsController(ApiClient api) : Controller
{
    private readonly ApiClient _api = api;

    public async Task<IActionResult> Index()
    {
        var overview = await _api.GetDashboardStatsAsync();
        var appointments = await _api.GetAppointmentStatsAsync(DateTime.UtcNow.AddDays(-30), DateTime.UtcNow);

        ViewData["AppointmentsChart"] = appointments;
        return View(overview);
    }
}

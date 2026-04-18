using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers;

public class DashboardController(ApiClient api) : Controller
{
    private readonly ApiClient _api = api;

    public async Task<IActionResult> Index()
    {
        var stats = await _api.GetDashboardStatsAsync();
        return View(stats);
    }
}

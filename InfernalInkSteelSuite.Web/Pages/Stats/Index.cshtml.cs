using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using Microsoft.AspNetCore.Http;

namespace InfernalInkSteelSuite.Web.Pages.Stats;

public class IndexModel(ApiClient api) : PageModel
{
    private readonly ApiClient _api = api;

    public ApiClient.DashboardStatsDto? Stats { get; set; }

    public async Task<IActionResult> OnGetAsync()
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
        {
            return RedirectToPage("/Account/Login");
        }

        var role = HttpContext.Session.GetString("Role");
        if (role != "Admin" && role != "Manager")
        {
            return RedirectToPage("/Dashboard/Index");
        }

        // Role checked above

        Stats = await _api.GetDashboardStatsAsync();
        return Page();
    }
}

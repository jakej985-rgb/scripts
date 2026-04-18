using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;

namespace InfernalInkSteelSuite.Web.Pages.Clients;

public class IndexModel(ApiClient api) : PageModel
{
    private readonly ApiClient _api = api;

    public List<ClientDto> Clients { get; set; } = [];

    [BindProperty(SupportsGet = true)]
    public string? Search { get; set; }

    public async Task<IActionResult> OnGetAsync()
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
            return RedirectToPage("/Account/Login");

        var all = await _api.GetClientsAsync();

        if (!string.IsNullOrWhiteSpace(Search))
        {
            var term = Search.Trim();
            Clients = [.. all.Where(c =>
                (!string.IsNullOrEmpty(c.FullName) && c.FullName.Contains(term, StringComparison.OrdinalIgnoreCase)) ||
                (!string.IsNullOrEmpty(c.Phone) && c.Phone.Contains(term, StringComparison.OrdinalIgnoreCase)) ||
                (!string.IsNullOrEmpty(c.Email) && c.Email.Contains(term, StringComparison.OrdinalIgnoreCase))
            )];
        }
        else
        {
            Clients = all;
        }

        return Page();
    }
}

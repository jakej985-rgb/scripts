using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using static InfernalInkSteelSuite.Web.Services.ApiClient;

namespace InfernalInkSteelSuite.Web.Pages.Quotes;

public class IndexModel(ApiClient api) : PageModel
{
    private readonly ApiClient _api = api;

    public List<QuoteDto> Quotes { get; set; } = [];

    public async Task<IActionResult> OnGetAsync()
    {
        var token = HttpContext.Session.GetString("ApiToken");
        if (string.IsNullOrEmpty(token))
            return RedirectToPage("/Account/Login");

        Quotes = await _api.GetAllQuotesAsync();
        Quotes = [.. Quotes.OrderByDescending(q => q.CreatedAt)];

        return Page();
    }
}

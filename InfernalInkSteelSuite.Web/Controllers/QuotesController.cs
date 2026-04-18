using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers;

public class QuotesController(ApiClient api) : Controller
{
    private readonly ApiClient _api = api;

    public async Task<IActionResult> Index()
    {
        var quotes = await _api.GetAllQuotesAsync();
        return View(quotes);
    }

    public IActionResult Create(int? clientId)
    {
        ViewData["ClientId"] = clientId;
        return View(new ApiClient.QuoteInput { ClientId = clientId });
    }

    [HttpPost]
    public async Task<IActionResult> Preview([FromBody] ApiClient.QuoteInput input)
    {
        var estimate = await _api.CalculateQuoteAsync(input);
        return Json(estimate);
    }

    [HttpPost]
    public async Task<IActionResult> Create(ApiClient.QuoteInput input)
    {
        // Get artist ID from session
        var artistId = HttpContext.Session.GetInt32("UserId") ?? 0;
        input.ArtistId = artistId;

        await _api.CreateQuoteAsync(input);
        return RedirectToAction("Index");
    }
}

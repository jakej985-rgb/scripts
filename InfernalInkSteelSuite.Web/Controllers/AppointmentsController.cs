using InfernalInkSteelSuite.Web.Models;
using InfernalInkSteelSuite.Web.Services;
using Microsoft.AspNetCore.Mvc;

namespace InfernalInkSteelSuite.Web.Controllers
{
    public class AppointmentsController(ApiClient api) : Controller
    {
        private readonly ApiClient _api = api;

        public async Task<IActionResult> Index()
        {
            var appointments = await _api.GetAppointmentsAsync()
                                ?? [];
            return View(appointments);
        }
    }
}

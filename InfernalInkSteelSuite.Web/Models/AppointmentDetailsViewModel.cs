using InfernalInkSteelSuite.Web.Services;

namespace InfernalInkSteelSuite.Web.Models;

public class AppointmentDetailsViewModel
{
    public AppointmentDto CurrentAppointment { get; set; } = null!;
    public List<AppointmentDto> PastSessions { get; set; } = [];
    public List<ApiClient.QuoteDto> AvailableQuotes { get; set; } = [];
}

using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.RazorPages;
using InfernalInkSteelSuite.Web.Models;
// In real app, inject Service/Repo

namespace InfernalInkSteelSuite.Web.Pages.Appointments
{
    public class PurgatoryModel : PageModel
    {
        public List<AppointmentDto> PendingAppts { get; set; } = new List<AppointmentDto>();
        public List<AppointmentDto> ConfirmedAppts { get; set; } = new List<AppointmentDto>();
        public List<AppointmentDto> CompletedAppts { get; set; } = new List<AppointmentDto>();

        public void OnGet()
        {
            // MOCKED DATA for demonstration
            // In production, this would use _appointmentRepository.GetAll()
            
            PendingAppts.Add(new AppointmentDto { Id = 101, ClientName = "John Doe", ServiceType = "Consultation", StartTime = DateTime.Today.AddHours(14), Status = "Pending" });
            PendingAppts.Add(new AppointmentDto { Id = 102, ClientName = "Jane Smith", ServiceType = "Flash Tattoo", StartTime = DateTime.Today.AddDays(1), Status = "Pending" });

            ConfirmedAppts.Add(new AppointmentDto { Id = 201, ClientName = "Mike Tyson", ServiceType = "Face Tattoo", StartTime = DateTime.Today.AddHours(10), Status = "Confirmed" });
            
            CompletedAppts.Add(new AppointmentDto { Id = 301, ClientName = "Old Client", ServiceType = "Cover Up", StartTime = DateTime.Today.AddDays(-5), Status = "Completed" });
        }
    }
}

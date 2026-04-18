using InfernalInkSteelSuite.Domain;
using System.Text.Json.Serialization;

namespace InfernalInkSteelSuite.Web.Models;

public class ClientDto
{
    public int Id { get; set; }
    public string FirstName { get; set; } = string.Empty;
    public string? MiddleName { get; set; }
    public string LastName { get; set; } = string.Empty;
    public string? Phone { get; set; }
    public string? Email { get; set; }
    public string? PhotoPath { get; set; }
    public string? Notes { get; set; }
    public int Visits { get; set; }

    [JsonConverter(typeof(JsonStringEnumConverter))]
    public ClientStatus Status { get; set; }

    public string FullName => string.Join(" ", new[] { FirstName, MiddleName, LastName }.Where(s => !string.IsNullOrWhiteSpace(s)));
}

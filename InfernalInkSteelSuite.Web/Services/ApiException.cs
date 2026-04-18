using System.Net;

namespace InfernalInkSteelSuite.Web.Services;

public class ApiException(HttpStatusCode statusCode, string content) : Exception(content)
{
    public HttpStatusCode StatusCode { get; } = statusCode;
    public string Content { get; } = content;
}

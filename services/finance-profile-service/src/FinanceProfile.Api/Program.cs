using FinanceProfile.Api.Application.Abstract;
using FinanceProfile.Api.Application.Concrete;
using FinanceProfile.Api.Infrastructure.Abstract;
using FinanceProfile.Api.Infrastructure.EntityFramework;
using FinanceProfile.Api.Infrastructure.External;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();

builder.Services.AddDbContext<FinanceDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("FinanceDb")));

builder.Services.AddScoped<IFinancialProfileDal, EfFinancialProfileDal>();
builder.Services.AddScoped<IFinancialProfileService, FinancialProfileManager>();
builder.Services.AddScoped<IFinancialIqClient, FinancialIqClient>();

builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddHttpClient("FinancialIqService", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["FinancialIqService:BaseUrl"]!);
});

builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(policy =>
    {
        policy.WithOrigins("http://localhost:5173")
              .AllowAnyHeader()
              .AllowAnyMethod();
    });
});

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseCors();

app.UseAuthorization();
app.MapControllers();
app.Run();
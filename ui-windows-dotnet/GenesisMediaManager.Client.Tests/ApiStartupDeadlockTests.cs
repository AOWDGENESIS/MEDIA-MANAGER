// Regression fuer den realen WPF-Start-Deadlock: MainWindow liest die
// Sprache synchron auf dem Dispatcher-Thread. Der darunterliegende
// HTTP-Handler darf bei keinem seiner awaits diesen Kontext festhalten.
// Der Test braucht weder Internet noch eine Windows-GUI.
using System.Net;
using System.Net.Http;
using System.Reflection;
using System.Text;
using GenesisMediaManager.Client.Api;
using Xunit;

namespace GenesisMediaManager.Client.Tests;

public class ApiStartupDeadlockTests
{
    // Ein WPF-Dispatcher, der gerade auf .GetResult() wartet, pumpt keine
    // Fortsetzungen. Post absichtlich NICHT ausfuehren.
    private sealed class BlockedUiContext : SynchronizationContext
    {
        public override void Post(SendOrPostCallback callback, object? state) { }
    }

    private sealed class DelayedJsonContent : HttpContent
    {
        protected override bool TryComputeLength(out long length)
        {
            length = 0;
            return false;
        }

        protected override async Task SerializeToStreamAsync(Stream stream, TransportContext? context)
        {
            await Task.Delay(30).ConfigureAwait(false);
            await stream.WriteAsync(Encoding.UTF8.GetBytes("{\"detail\":\"not authorized\"}"))
                .ConfigureAwait(false);
        }
    }

    private sealed class DelayedResponseHandler(bool success) : HttpMessageHandler
    {
        protected override async Task<HttpResponseMessage> SendAsync(
            HttpRequestMessage request, CancellationToken cancellationToken)
        {
            await Task.Delay(30, cancellationToken).ConfigureAwait(false);
            return new HttpResponseMessage(success ? HttpStatusCode.OK : HttpStatusCode.Unauthorized)
            {
                Content = success ? new StringContent("{}") : new DelayedJsonContent(),
            };
        }
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void ErrorHandlerDoesNotDeadlockWhenUiThreadBlocksOnSettings(bool success)
    {
        // Testet den ECHTEN verschachtelten Handler und beide Pfade
        // (Erfolg sowie die spaeter asynchron eingelesene Fehlerantwort).
        var type = typeof(GenesisApiClient).GetNestedType(
            "ApiErrorDetailHandler", BindingFlags.NonPublic);
        Assert.NotNull(type);
        using var handler = (DelegatingHandler)Activator.CreateInstance(type!, nonPublic: true)!;
        handler.InnerHandler = new DelayedResponseHandler(success);
        using var invoker = new HttpMessageInvoker(handler);
        Exception? error = null;
        HttpStatusCode? status = null;

        var blockedThread = new Thread(() =>
        {
            SynchronizationContext.SetSynchronizationContext(new BlockedUiContext());
            try
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, "http://127.0.0.1/settings");
                // xUnit1031 gilt fuer normale Tests; hier ist der BLOCKIERTE
                // UI-Thread genau die Bedingung, deren Regression wir pruefen.
#pragma warning disable xUnit1031
                using var response = invoker.SendAsync(request, CancellationToken.None)
                    .GetAwaiter().GetResult();
#pragma warning restore xUnit1031
                status = response.StatusCode;
            }
            catch (Exception ex)
            {
                error = ex;
            }
            finally
            {
                SynchronizationContext.SetSynchronizationContext(null);
            }
        }) { IsBackground = true };

        blockedThread.Start();
        Assert.True(blockedThread.Join(TimeSpan.FromSeconds(5)),
            "Der HTTP-Handler wartet auf den blockierten UI-Kontext (Start-Deadlock).");
        if (success)
        {
            Assert.Null(error);
            Assert.Equal(HttpStatusCode.OK, status);
        }
        else
        {
            var apiError = Assert.IsType<GenesisApiException>(error);
            Assert.Equal("not authorized", apiError.Message);
        }
    }
}

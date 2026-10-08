// Tests fuer die WPF-unabhaengige Hilfslogik der Cover-Vorschau
// (MediaCoverSupport.cs). Spiegelt die Kernfaelle, die auf Python-Seite in
// ui-reference-pyside/tests/test_media_table*.py fuer
// pixmap_from_artwork_bytes abgedeckt sind, soweit sie sich ohne echtes
// Qt/WPF-Bild-Decoding pruefen lassen (reine Signatur-/Magic-Bytes-Erkennung).
namespace GenesisMediaManager.Client.Tests;

public class MediaCoverSupportTests
{
    [Fact]
    public void LooksLikeDecodableImage_NullData_ReturnsFalse()
    {
        Assert.False(MediaCoverSupport.LooksLikeDecodableImage(null));
    }

    [Fact]
    public void LooksLikeDecodableImage_EmptyData_ReturnsFalse()
    {
        Assert.False(MediaCoverSupport.LooksLikeDecodableImage(Array.Empty<byte>()));
    }

    [Fact]
    public void LooksLikeDecodableImage_TooShortData_ReturnsFalse()
    {
        Assert.False(MediaCoverSupport.LooksLikeDecodableImage(new byte[] { 0x89, 0x50 }));
    }

    [Fact]
    public void LooksLikeDecodableImage_GarbageData_ReturnsFalse()
    {
        Assert.False(MediaCoverSupport.LooksLikeDecodableImage(new byte[] { 0x00, 0x01, 0x02, 0x03, 0x04 }));
    }

    [Fact]
    public void LooksLikeDecodableImage_PngSignature_ReturnsTrue()
    {
        var data = new byte[] { 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A };
        Assert.True(MediaCoverSupport.LooksLikeDecodableImage(data));
    }

    [Fact]
    public void LooksLikeDecodableImage_JpegSignature_ReturnsTrue()
    {
        var data = new byte[] { 0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10 };
        Assert.True(MediaCoverSupport.LooksLikeDecodableImage(data));
    }

    [Fact]
    public void LooksLikeDecodableImage_GifSignature_ReturnsTrue()
    {
        var data = System.Text.Encoding.ASCII.GetBytes("GIF89a");
        Assert.True(MediaCoverSupport.LooksLikeDecodableImage(data));
    }

    [Fact]
    public void LooksLikeDecodableImage_BmpSignature_ReturnsTrue()
    {
        var data = new byte[] { 0x42, 0x4D, 0x00, 0x00, 0x00, 0x00 };
        Assert.True(MediaCoverSupport.LooksLikeDecodableImage(data));
    }

    [Fact]
    public void LooksLikeDecodableImage_WebpSignature_ReturnsTrue()
    {
        var data = new byte[]
        {
            0x52, 0x49, 0x46, 0x46, 0x00, 0x00, 0x00, 0x00,
            0x57, 0x45, 0x42, 0x50,
        };
        Assert.True(MediaCoverSupport.LooksLikeDecodableImage(data));
    }
}

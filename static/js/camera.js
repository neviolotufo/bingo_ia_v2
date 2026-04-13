let currentStream = null;
let useFront = false;

const video = document.getElementById("cameraVideo");
const canvas = document.getElementById("cameraCanvas");
const capturedImage = document.getElementById("capturedImage");
const previewCapture = document.getElementById("previewCapture");
const startCameraBtn = document.getElementById("startCameraBtn");
const switchCameraBtn = document.getElementById("switchCameraBtn");
const captureBtn = document.getElementById("captureBtn");
const mobileCameraInput = document.getElementById("mobileCameraInput");

function showError(message) {
    alert(message);
}

function stopCurrentStream() {
    if (currentStream) {
        currentStream.getTracks().forEach(track => track.stop());
        currentStream = null;
    }
}

function isGetUserMediaAvailable() {
    return !!(
        navigator.mediaDevices &&
        typeof navigator.mediaDevices.getUserMedia === "function"
    );
}

async function startCamera() {
    if (!isGetUserMediaAvailable()) {
        showError(
            "A câmera em tempo real não está disponível neste navegador/endereço.\n\n" +
            "Use o botão 'Abrir câmera do celular' para tirar a foto pelo app nativo da câmera."
        );
        return;
    }

    try {
        stopCurrentStream();

        const constraints = {
            audio: false,
            video: {
                facingMode: useFront ? "user" : { ideal: "environment" },
                width: { ideal: 1920 },
                height: { ideal: 1080 }
            }
        };

        currentStream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = currentStream;
        await video.play();
    } catch (err) {
        showError("Não foi possível acessar a câmera: " + err.message);
    }
}

function capturePhoto() {
    if (!video.videoWidth || !video.videoHeight) {
        showError("A câmera ainda não está pronta.");
        return;
    }

    const vw = video.videoWidth;
    const vh = video.videoHeight;

    canvas.width = vw;
    canvas.height = vh;

    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, vw, vh);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    capturedImage.value = dataUrl;
    previewCapture.src = dataUrl;
    previewCapture.classList.remove("d-none");
}

function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
}

async function handleMobileCapture(event) {
    const file = event.target.files?.[0];
    if (!file) return;

    try {
        const dataUrl = await readFileAsDataURL(file);
        capturedImage.value = dataUrl;
        previewCapture.src = dataUrl;
        previewCapture.classList.remove("d-none");
    } catch (err) {
        showError("Erro ao carregar a foto capturada.");
    }
}

startCameraBtn?.addEventListener("click", startCamera);

switchCameraBtn?.addEventListener("click", async () => {
    useFront = !useFront;
    await startCamera();
});

captureBtn?.addEventListener("click", capturePhoto);

mobileCameraInput?.addEventListener("change", handleMobileCapture);

window.addEventListener("beforeunload", stopCurrentStream);
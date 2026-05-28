package com.barcodescanner

import android.graphics.Bitmap
import android.graphics.Rect
import android.os.Bundle
import android.widget.Button
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import org.tensorflow.lite.Interpreter
import java.io.FileInputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.MappedByteBuffer
import java.nio.channels.FileChannel
import java.util.concurrent.Executors
import com.google.zxing.BinaryBitmap
import com.google.zxing.MultiFormatReader
import com.google.zxing.RGBLuminanceSource
import com.google.zxing.common.GlobalHistogramBinarizer

class MainActivity : AppCompatActivity() {

    private lateinit var overlayView: OverlayView
    private lateinit var btnFinish: Button
    private lateinit var tvStatus: TextView
    private lateinit var previewView: PreviewView
    private val memory = BarcodeMemory()

    private var tfliteInterpreter: Interpreter? = null
    private val inputSize = 640
    private var lastBitmap: Bitmap? = null
    private var logSaved = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        overlayView = findViewById(R.id.overlay)
        btnFinish = findViewById(R.id.btn_finish)
        tvStatus = findViewById(R.id.tv_status)
        previewView = findViewById(R.id.previewView)

        tfliteInterpreter = Interpreter(loadModelFile("best_float32.tflite"))
        startCamera()

        val btnSave: Button = findViewById(R.id.btn_save)
        btnSave.setOnClickListener {
            lastBitmap?.let { bmp ->
                try {
                    val dir = android.os.Environment.getExternalStoragePublicDirectory(
                        android.os.Environment.DIRECTORY_DOWNLOADS
                    )
                    val file = java.io.File(dir, "test_frame.jpg")
                    java.io.FileOutputStream(file).use { fos ->
                        bmp.compress(Bitmap.CompressFormat.JPEG, 100, fos)
                    }
                    tvStatus.text = "Кадр сохранён"
                } catch (e: Exception) {
                    tvStatus.text = "Ошибка сохранения"
                }
            } ?: run { tvStatus.text = "Нет кадра" }
        }

        btnFinish.setOnClickListener {
            val all = memory.getAll()
            if (all.isEmpty()) {
                tvStatus.text = "Нет прочитанных кодов"
                return@setOnClickListener
            }
            val json = BarcodeApi.toJson(all)
            try {
                val dir = android.os.Environment.getExternalStoragePublicDirectory(
                    android.os.Environment.DIRECTORY_DOWNLOADS
                )
                val file = java.io.File(dir, "barcodes.json")
                file.writeText(json)
                tvStatus.text = "Сохранено: ${all.size} кодов в Downloads"
                memory.clear()
                overlayView.hasDetection = false
                overlayView.invalidate()
            } catch (e: Exception) {
                tvStatus.text = "Ошибка сохранения JSON"
            }
        }
    }

    private fun loadModelFile(filename: String): MappedByteBuffer {
        val descriptor = assets.openFd(filename)
        val inputStream = FileInputStream(descriptor.fileDescriptor)
        return inputStream.channel.map(
            FileChannel.MapMode.READ_ONLY,
            descriptor.startOffset,
            descriptor.declaredLength
        )
    }

    private fun startCamera() {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(this)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            val preview = androidx.camera.core.Preview.Builder().build()
            preview.setSurfaceProvider(previewView.surfaceProvider)

            val imageAnalysis = ImageAnalysis.Builder()
                .setTargetResolution(android.util.Size(1920, 1080))
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()

            imageAnalysis.setAnalyzer(Executors.newSingleThreadExecutor()) { imageProxy ->
                processFrame(imageProxy)
            }

            val cameraSelector = CameraSelector.DEFAULT_BACK_CAMERA
            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(this, cameraSelector, preview, imageAnalysis)
            } catch (e: Exception) {
                tvStatus.text = "Ошибка камеры: ${e.message}"
            }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun processFrame(imageProxy: ImageProxy) {
        val logLines = StringBuilder()
        val bitmap = imageProxy.toBitmap()

        val rotation = imageProxy.imageInfo.rotationDegrees
        val rotatedBitmap = if (rotation != 0) {
            val matrix = android.graphics.Matrix().apply { postRotate(rotation.toFloat()) }
            Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        } else bitmap

        lastBitmap = rotatedBitmap
        val w = rotatedBitmap.width.toFloat()
        val h = rotatedBitmap.height.toFloat()

        val previewW = previewView.width.toFloat()
        val previewH = previewView.height.toFloat()
        val scale = minOf(previewW / w, previewH / h)
        val offsetX = (previewW - w * scale) / 2
        val offsetY = (previewH - h * scale) / 2

        logLines.append("Image: ${rotatedBitmap.width}x${rotatedBitmap.height} inputSize=$inputSize\n")
        logLines.append("Preview: ${previewView.width}x${previewView.height}\n\n")

        val resized = Bitmap.createScaledBitmap(rotatedBitmap, inputSize, inputSize, true)
        val inputBuffer = preprocess(resized)
        val outputBuffer = Array(1) { Array(6) { FloatArray(8400) } }
        tfliteInterpreter?.run(inputBuffer, outputBuffer)

        val raw = outputBuffer[0]
        var detections = 0
        val foundBoxes = mutableListOf<Rect>()

        for (i in 0 until 8400) {
            val conf = raw[4][i]
            if (conf < 0.4f) continue
            detections++

            val x_center = raw[0][i]
            val y_center = raw[1][i]
            val width    = raw[2][i]
            val height   = raw[3][i]

            if (detections <= 10) {
                logLines.append("Det $detections: xc=${"%.4f".format(x_center)} yc=${"%.4f".format(y_center)} w=${"%.4f".format(width)} h=${"%.4f".format(height)} conf=${"%.4f".format(conf)}\n")
            }

            val cx = x_center * w
            val cy = y_center * h

            // Перебор масштабов: 1.0, 1.5, 2.0, 2.5
            var bestText: String? = null
            var bestRect: Rect? = null
            for (factor in floatArrayOf(1.0f, 1.5f, 2.0f, 2.5f)) {
                val bw = width * w * factor
                val bh = height * h * factor

                var x1 = (cx - bw / 2).toInt()
                var y1 = (cy - bh / 2).toInt()
                var x2 = (cx + bw / 2).toInt()
                var y2 = (cy + bh / 2).toInt()

                x1 = maxOf(0, x1)
                y1 = maxOf(0, y1)
                x2 = minOf(w.toInt(), x2)
                y2 = minOf(h.toInt(), y2)

                if (x2 - x1 < 10 || y2 - y1 < 10) continue

                val crop = Bitmap.createBitmap(rotatedBitmap, x1, y1, x2 - x1, y2 - y1)
                val text = tryReadWithZxing(crop)
                if (text != null) {
                    bestText = text
                    bestRect = Rect(x1, y1, x2, y2)
                    break
                }
            }

            if (bestText != null && bestRect != null) {
                foundBoxes.add(bestRect)
                if (memory.add(bestText, bestRect, raw[4][i])) {
                    val scaledRect = Rect(
                        (bestRect.left * scale + offsetX).toInt(),
                        (bestRect.top * scale + offsetY).toInt(),
                        (bestRect.right * scale + offsetX).toInt(),
                        (bestRect.bottom * scale + offsetY).toInt()
                    )
                    runOnUiThread {
                        overlayView.addReadBox(bestText, scaledRect)
                    }
                }
            } else {
                // Если не прочитан — добавляем исходный бокс
                val bw = width * w * 2f
                val bh = height * h * 2f
                var x1 = (cx - bw / 2).toInt()
                var y1 = (cy - bh / 2).toInt()
                var x2 = (cx + bw / 2).toInt()
                var y2 = (cy + bh / 2).toInt()
                x1 = maxOf(0, x1); y1 = maxOf(0, y1)
                x2 = minOf(w.toInt(), x2); y2 = minOf(h.toInt(), y2)
                if (x2 - x1 >= 10 && y2 - y1 >= 10) {
                    foundBoxes.add(Rect(x1, y1, x2, y2))
                }
            }
        }

        if (detections > 0 && !logSaved) {
            logSaved = true
            logLines.insert(0, "Detections: $detections\n\n")
            try {
                val dir = android.os.Environment.getExternalStoragePublicDirectory(
                    android.os.Environment.DIRECTORY_DOWNLOADS
                )
                val file = java.io.File(dir, "yolo_debug.txt")
                file.writeText(logLines.toString())
            } catch (_: Exception) {}
        }

        runOnUiThread {
            overlayView.hasDetection = detections > 0
            overlayView.invalidate()
            tvStatus.text = "Det: $detections | Read: ${memory.size()}"
        }
        imageProxy.close()
    }

    private fun preprocess(bitmap: Bitmap): ByteBuffer {
        val buffer = ByteBuffer.allocateDirect(4 * inputSize * inputSize * 3)
        buffer.order(ByteOrder.nativeOrder())
        val pixels = IntArray(inputSize * inputSize)
        bitmap.getPixels(pixels, 0, inputSize, 0, 0, inputSize, inputSize)
        for (pixel in pixels) {
            buffer.putFloat(((pixel shr 16) and 0xFF) / 255.0f)
            buffer.putFloat(((pixel shr 8) and 0xFF) / 255.0f)
            buffer.putFloat((pixel and 0xFF) / 255.0f)
        }
        return buffer
    }

    private fun tryReadWithZxing(bitmap: Bitmap): String? {
        return try {
            // 1. Усиление контраста (аналог CLAHE)
            val contrast = 1.8f
            val cm = android.graphics.ColorMatrix(floatArrayOf(
                contrast, 0f, 0f, 0f, 128 * (1 - contrast),
                0f, contrast, 0f, 0f, 128 * (1 - contrast),
                0f, 0f, contrast, 0f, 128 * (1 - contrast),
                0f, 0f, 0f, 1f, 0f
            ))
            val paint = android.graphics.Paint()
            paint.colorFilter = android.graphics.ColorMatrixColorFilter(cm)
            val enhanced = Bitmap.createBitmap(bitmap.width, bitmap.height, Bitmap.Config.ARGB_8888)
            val canvas = android.graphics.Canvas(enhanced)
            canvas.drawBitmap(bitmap, 0f, 0f, paint)

            // 2. Бинаризация с адаптивным порогом
            val width = enhanced.width
            val height = enhanced.height
            val pixels = IntArray(width * height)
            enhanced.getPixels(pixels, 0, width, 0, 0, width, height)

            var sum = 0
            for (p in pixels) {
                val gray = ((p shr 16 and 0xFF) * 0.299 + (p shr 8 and 0xFF) * 0.587 + (p and 0xFF) * 0.114).toInt()
                sum += gray
            }
            val threshold = (sum / pixels.size * 0.85).toInt()

            val binaryPixels = IntArray(width * height)
            for (i in pixels.indices) {
                val gray = ((pixels[i] shr 16 and 0xFF) * 0.299 + (pixels[i] shr 8 and 0xFF) * 0.587 + (pixels[i] and 0xFF) * 0.114).toInt()
                binaryPixels[i] = if (gray < threshold) 0xFF000000.toInt() else 0xFFFFFFFF.toInt()
            }

            val source = RGBLuminanceSource(width, height, binaryPixels)
            val binarizer = GlobalHistogramBinarizer(source)
            val binaryBitmap = BinaryBitmap(binarizer)
            val result = MultiFormatReader().decode(binaryBitmap)
            val text = result.text
            // Проверяем, что это похоже на штрихкод (только цифры, 8-14 символов)
            if (text.matches(Regex("^[0-9]{12,14}$"))) {
                text
            } else {
                null
            }
        } catch (e: Exception) {
            null
        }
    }
}
from aiogram import Router, types
from aiogram.types import CallbackQuery
from database import get_active_subscription

router = Router()

INSTRUCTIONS = {
    "windows": """
🖥 Инструкция по настройке WireGuard для Windows:

1. Скачайте и установите WireGuard с официального сайта:
   https://www.wireguard.com/install/

2. Запустите WireGuard

3. Нажмите кнопку "Import tunnel(s) from file"

4. Выберите скачанный файл конфигурации

5. Нажмите "Activate" для подключения

Готово! Теперь вы подключены к VPN 🎉
""",
    
    "macos": """
🍎 Инструкция по настройке WireGuard для MacOS:

1. Установите WireGuard из App Store или с официального сайта:
   https://www.wireguard.com/install/

2. Откройте приложение WireGuard

3. Нажмите "File" -> "Import tunnel(s) from file"

4. Выберите скачанный файл конфигурации

5. Нажмите кнопку "Activate" для подключения

Готово! Теперь вы подключены к VPN 🎉
""",
    
    "linux": """
🐧 Инструкция по настройке WireGuard для Linux:

1. Установите WireGuard:
   Ubuntu/Debian: sudo apt install wireguard
   Fedora: sudo dnf install wireguard-tools

2. Сохраните конфигурацию в файл:
   sudo nano /etc/wireguard/wg0.conf

3. Вставьте содержимое конфигурации и сохраните (Ctrl+X, Y, Enter)

4. Запустите WireGuard:
   sudo wg-quick up wg0

5. Для автозапуска:
   sudo systemctl enable wg-quick@wg0

Готово! Теперь вы подключены к VPN 🎉
""",
    
    "ios": """
📱 Инструкция по настройке WireGuard для iOS:

1. Установите приложение WireGuard из App Store

2. Откройте приложение

3. Нажмите "+" и выберите "Create from QR code"

4. Отсканируйте QR-код ниже

5. Нажмите "Allow" для добавления конфигурации VPN

6. Включите переключатель для подключения

Готово! Теперь вы подключены к VPN 🎉
""",
    
    "android": """
🤖 Инструкция по настройке WireGuard для Android:

1. Установите приложение WireGuard из Google Play

2. Откройте приложение

3. Нажмите "+" и выберите "Scan from QR code"

4. Отсканируйте QR-код ниже

5. Разрешите создание VPN-подключения

6. Нажмите на переключатель для подключения

Готово! Теперь вы подключены к VPN 🎉
"""
}

@router.callback_query(lambda c: c.data.startswith("config_"))
async def send_config(callback: CallbackQuery):
    """Отправляет конфигурацию и инструкции для выбранной ОС"""
    os_type, user_id = callback.data.split("_")[1:]
    user_id = int(user_id)
    
    if callback.from_user.id != user_id:
        await callback.answer("Это не ваша конфигурация!", show_alert=True)
        return
    
    sub = await get_active_subscription(user_id)
    if not sub:
        await callback.answer("У вас нет активной подписки!", show_alert=True)
        return
    
    # Получаем инструкции для выбранной ОС
    instructions = INSTRUCTIONS.get(os_type.lower())
    if not instructions:
        await callback.answer("Неподдерживаемая операционная система!", show_alert=True)
        return
    
    # Отправляем инструкции
    await callback.message.answer(instructions)
    
    # Отправляем файл конфигурации
    config_file = f"wireguard_{user_id}.conf"
    with open(config_file, "w") as f:
        f.write(sub["config"])
    
    await callback.message.answer_document(
        types.FSInputFile(config_file),
        caption="📝 Ваш файл конфигурации WireGuard"
    )
    
    # Если это мобильная ОС, отправляем QR-код
    if os_type.lower() in ["ios", "android"]:
        await callback.message.answer_photo(
            types.FSInputFile(f"qr_{user_id}.png"),
            caption="📱 QR-код для быстрой настройки"
        )
    
    await callback.answer() 
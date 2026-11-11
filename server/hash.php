<?php
echo "The valid BCRYPT hash for 1234 is: <br><br>";
echo password_hash('1234', PASSWORD_BCRYPT);
?>

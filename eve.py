import pygame
import math
import random
import sqlite3

# ---------------- Database Functions -----------------
def init_db():
    conn = sqlite3.connect("highscores.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS highscores (name TEXT, score INTEGER)")
    conn.commit()
    conn.close()

def save_score(name, score):
    conn = sqlite3.connect("highscores.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO highscores (name, score) VALUES (?, ?)", (name, score))
    conn.commit()
    conn.close()

def get_top_scores():
    conn = sqlite3.connect("highscores.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, score FROM highscores ORDER BY score DESC LIMIT 3")
    results = cursor.fetchall()
    conn.close()
    return results

# Initialize the database.
init_db()

# ---------------- Pygame Initialization -----------------
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Advanced EVE-Style Space Combat")
clock = pygame.time.Clock()
FPS = 60

# ---------------- Colors -----------------
BLACK    = (0, 0, 0)
WHITE    = (255, 255, 255)
YELLOW   = (255, 255, 0)
RED      = (255, 0, 0)
GREEN    = (0, 255, 0)
ORANGE   = (255, 165, 0)
CYAN     = (0, 255, 255)
BLUE     = (0, 0, 255)

# ---------------- Starfield Layers -----------------
NUM_STARS_FAR = 100
NUM_STARS_NEAR = 50
stars_far = [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(NUM_STARS_FAR)]
stars_near = [(random.randint(0, WIDTH), random.randint(0, HEIGHT)) for _ in range(NUM_STARS_NEAR)]

# ---------------- Global Mode Variables -----------------
# selected_mode: 1 = Standard, 2 = Less Aggressive (75% less aggression)
selected_mode = 1
enemy_aggression_factor = 1.0  # Will be set based on mode selection when game starts

# ---------------- Spaceship Classes -----------------
class Spaceship:
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        self.color = color
        self.angle = 0  # Degrees; 0 means facing right.
        self.velocity = pygame.math.Vector2(0, 0)
        self.acceleration = 0.2
        self.rotation_speed = 3
        self.max_speed = 5
        self.radius = 15
        self.health = 100
        self.last_shot = pygame.time.get_ticks()
        self.shot_cooldown = 500  # milliseconds
        self.thrust = False

    def update(self):
        self.x += self.velocity.x
        self.y += self.velocity.y
        self.velocity *= 0.99
        # Wrap around screen edges.
        if self.x > WIDTH: self.x = 0
        elif self.x < 0: self.x = WIDTH
        if self.y > HEIGHT: self.y = 0
        elif self.y < 0: self.y = HEIGHT

    def draw(self, surface):
        tip = pygame.math.Vector2(self.radius, 0).rotate(-self.angle)
        left = pygame.math.Vector2(-self.radius/2, self.radius/1.5).rotate(-self.angle)
        right = pygame.math.Vector2(-self.radius/2, -self.radius/1.5).rotate(-self.angle)
        p1 = (self.x + tip.x, self.y + tip.y)
        p2 = (self.x + left.x, self.y + left.y)
        p3 = (self.x + right.x, self.y + right.y)
        pygame.draw.polygon(surface, self.color, [p1, p2, p3])
        # Draw thruster flame.
        if self.thrust:
            flame = pygame.math.Vector2(-self.radius - 5, 0).rotate(-self.angle)
            flame_left = pygame.math.Vector2(-self.radius/2 - 5, self.radius/3).rotate(-self.angle)
            flame_right = pygame.math.Vector2(-self.radius/2 - 5, -self.radius/3).rotate(-self.angle)
            f1 = (self.x + flame.x, self.y + flame.y)
            f2 = (self.x + flame_left.x, self.y + flame_left.y)
            f3 = (self.x + flame_right.x, self.y + flame_right.y)
            pygame.draw.polygon(surface, ORANGE, [f1, f2, f3])

    def can_shoot(self):
        now = pygame.time.get_ticks()
        if now - self.last_shot >= self.shot_cooldown:
            self.last_shot = now
            return True
        return False

    def shoot(self):
        direction = pygame.math.Vector2(1, 0).rotate(-self.angle)
        bullet_velocity = self.velocity + direction * 10
        # Bullets from the player's ship have owner "player"
        return Bullet(self.x, self.y, bullet_velocity, self.color, owner="player")

# ---------------- Bullet Class with Owner Attribute -----------------
class Bullet:
    def __init__(self, x, y, velocity, color, owner="player"):
        self.x = x
        self.y = y
        self.velocity = velocity
        self.radius = 3
        self.color = color
        self.lifetime = 2000
        self.spawn_time = pygame.time.get_ticks()
        self.owner = owner  # "player" or "drone"

    def update(self):
        self.x += self.velocity.x
        self.y += self.velocity.y
        if self.x > WIDTH or self.x < 0 or self.y > HEIGHT or self.y < 0:
            self.lifetime = 0

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

class Explosion:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.radius = 5
        self.growth_rate = 1.5
        self.alpha = 255

    def update(self):
        self.radius += self.growth_rate
        self.alpha -= 5
        if self.alpha < 0:
            self.alpha = 0

    def draw(self, surface):
        explosion_surf = pygame.Surface((int(self.radius*2), int(self.radius*2)), pygame.SRCALPHA)
        pygame.draw.circle(explosion_surf, (255, 165, 0, int(self.alpha)), (int(self.radius), int(self.radius)), int(self.radius))
        surface.blit(explosion_surf, (self.x - self.radius, self.y - self.radius))

class AI_Chaser(Spaceship):
    def __init__(self, x, y, color):
        super().__init__(x, y, color)
        self.shot_cooldown = 1000

    def update_ai(self, target):
        direction = pygame.math.Vector2(target.x - self.x, target.y - self.y)
        desired_angle = math.degrees(math.atan2(-direction.y, direction.x))
        angle_diff = (desired_angle - self.angle + 180) % 360 - 180
        if angle_diff > 0:
            self.angle += min(self.rotation_speed, angle_diff)
        else:
            self.angle += max(-self.rotation_speed, angle_diff)
        if direction.length() > 150:
            forward = pygame.math.Vector2(1, 0).rotate(-self.angle)
            self.velocity += forward * self.acceleration * 0.5
            if self.velocity.length() > self.max_speed:
                self.velocity.scale_to_length(self.max_speed)
        else:
            self.velocity *= 0.95
        if abs(angle_diff) < 10 and self.can_shoot():
            return self.shoot()
        return None

class AI_Sniper(Spaceship):
    def __init__(self, x, y, color):
        super().__init__(x, y, color)
        self.shot_cooldown = 1500

    def update_ai(self, target):
        direction = pygame.math.Vector2(target.x - self.x, target.y - self.y)
        distance = direction.length()
        desired_angle = math.degrees(math.atan2(-direction.y, direction.x))
        angle_diff = (desired_angle - self.angle + 180) % 360 - 180
        if distance < 200:
            if direction.length() != 0:
                self.velocity += (-direction).normalize() * self.acceleration
        elif distance > 500:
            if direction.length() != 0:
                self.velocity += direction.normalize() * self.acceleration
        else:
            if direction.length() != 0:
                perp = pygame.math.Vector2(-direction.y, direction.x).normalize()
                self.velocity += perp * (self.acceleration * 0.5)
        if self.velocity.length() > self.max_speed:
            self.velocity.scale_to_length(self.max_speed)
        if angle_diff > 0:
            self.angle += min(self.rotation_speed, angle_diff)
        else:
            self.angle += max(-self.rotation_speed, angle_diff)
        if abs(angle_diff) < 15 and self.can_shoot():
            return self.shoot()
        return None

class Drone(Spaceship):
    def __init__(self, x, y, player):
        super().__init__(x, y, CYAN)
        self.player = player
        self.health = 50
        self.max_speed = 6
        self.acceleration = 0.3
        self.rotation_speed = 4
        self.radius = 10
        self.shot_cooldown = 800

    def update_ai(self, enemies):
        if enemies:
            target = min(enemies, key=lambda enemy: math.hypot(enemy.x - self.x, enemy.y - self.y))
        else:
            target = self.player
        direction = pygame.math.Vector2(target.x - self.x, target.y - self.y)
        desired_angle = math.degrees(math.atan2(-direction.y, direction.x))
        angle_diff = (desired_angle - self.angle + 180) % 360 - 180
        if angle_diff > 0:
            self.angle += min(self.rotation_speed, angle_diff)
        else:
            self.angle += max(-self.rotation_speed, angle_diff)
        if direction.length() > 50:
            forward = pygame.math.Vector2(1, 0).rotate(-self.angle)
            self.velocity += forward * self.acceleration
            if self.velocity.length() > self.max_speed:
                self.velocity.scale_to_length(self.max_speed)
        else:
            self.velocity *= 0.95
        if enemies and abs(angle_diff) < 10 and direction.length() < 200 and self.can_shoot():
            return self.shoot()
        return None

    # Override shoot so that drone bullets have owner "drone"
    def shoot(self):
        direction = pygame.math.Vector2(1, 0).rotate(-self.angle)
        bullet_velocity = self.velocity + direction * 10
        return Bullet(self.x, self.y, bullet_velocity, self.color, owner="drone")

# ---------------- Spawn Enemies with Mode-Based Aggression -----------------
def spawn_enemies(wave):
    enemies = []
    num_chasers = wave + 1
    num_snipers = max(1, wave - 1)
    for _ in range(num_chasers):
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top':
            x, y = random.randint(0, WIDTH), 0
        elif side == 'bottom':
            x, y = random.randint(0, WIDTH), HEIGHT
        elif side == 'left':
            x, y = 0, random.randint(0, HEIGHT)
        else:
            x, y = WIDTH, random.randint(0, HEIGHT)
        enemy = AI_Chaser(x, y, RED)
        # Modify enemy parameters based on aggression factor.
        enemy.acceleration *= enemy_aggression_factor
        enemy.rotation_speed *= enemy_aggression_factor
        enemy.shot_cooldown = int(enemy.shot_cooldown / enemy_aggression_factor)
        enemies.append(enemy)
    for _ in range(num_snipers):
        side = random.choice(['top', 'bottom', 'left', 'right'])
        if side == 'top':
            x, y = random.randint(0, WIDTH), 0
        elif side == 'bottom':
            x, y = random.randint(0, WIDTH), HEIGHT
        elif side == 'left':
            x, y = 0, random.randint(0, HEIGHT)
        else:
            x, y = WIDTH, random.randint(0, HEIGHT)
        enemy = AI_Sniper(x, y, GREEN)
        enemy.acceleration *= enemy_aggression_factor
        enemy.rotation_speed *= enemy_aggression_factor
        enemy.shot_cooldown = int(enemy.shot_cooldown / enemy_aggression_factor)
        enemies.append(enemy)
    return enemies

# ---------------- Game Variables and Reset Function -----------------
def reset_game():
    player = Spaceship(WIDTH // 2, HEIGHT // 2, YELLOW)
    bullets = []
    enemy_bullets = []
    drones = []
    enemies = spawn_enemies(1)
    explosions = []
    score = 0
    wave = 1
    force_field_active = False
    force_field_start_time = 0
    free_force_field_count = 0  # Count of free force field activations used so far
    tokens = 0
    return (player, bullets, enemy_bullets, drones, enemies, explosions, score, wave,
            force_field_active, force_field_start_time, free_force_field_count, tokens)

# Force field duration (20 seconds now)
FORCE_FIELD_DURATION = 20000

# ---------------- Game States and Name/Mode Input -----------------
# States: "start", "playing", "game_over"
state = "start"
player_name = ""  # Name entered by the player.
score_saved = False  # To avoid multiple score saves.
text_box_active = False  # Whether the text box is active

# Initialize game variables (will be reset when starting game)
(player, bullets, enemy_bullets, drones, enemies, explosions, score, wave,
 force_field_active, force_field_start_time, free_force_field_count, tokens) = reset_game()

# ---------------- Main Game Loop -----------------
running = True
while running:
    dt = clock.tick(FPS)
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if state == "start":
            if event.type == pygame.MOUSEBUTTONUP:
                mouse_pos = event.pos
                text_box_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 60, 300, 40)
                play_button_rect = pygame.Rect(WIDTH//2 - 75, HEIGHT//2 + 80, 150, 50)
                if text_box_rect.collidepoint(mouse_pos):
                    text_box_active = True
                else:
                    text_box_active = False
                if play_button_rect.collidepoint(mouse_pos):
                    if player_name == "":
                        player_name = "Player"
                    enemy_aggression_factor = 1.0 if selected_mode == 1 else 0.25
                    (player, bullets, enemy_bullets, drones, enemies, explosions, score, wave,
                     force_field_active, force_field_start_time, free_force_field_count, tokens) = reset_game()
                    score_saved = False
                    state = "playing"
            if event.type == pygame.KEYDOWN:
                # Mode selection.
                if event.key == pygame.K_1:
                    selected_mode = 1
                elif event.key == pygame.K_2:
                    selected_mode = 2
                if text_box_active:
                    if event.key == pygame.K_BACKSPACE:
                        player_name = player_name[:-1]
                    else:
                        if event.unicode.isprintable():
                            player_name += event.unicode

        elif state == "game_over":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    state = "start"
                elif event.key == pygame.K_q:
                    running = False

        elif state == "playing":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_f:
                    # Deploy 3 drones.
                    for i in range(3):
                        offset_angle = i * 120
                        offset = pygame.math.Vector2(30, 0).rotate(offset_angle)
                        drone_x = player.x + offset.x
                        drone_y = player.y + offset.y
                        drones.append(Drone(drone_x, drone_y, player))
                if event.key == pygame.K_j:
                    if not force_field_active:
                        # First 5 activations are free.
                        if free_force_field_count < 5:
                            free_force_field_count += 1
                            force_field_active = True
                            force_field_start_time = pygame.time.get_ticks()
                        else:
                            if tokens >= 1:
                                tokens -= 1
                                force_field_active = True
                                force_field_start_time = pygame.time.get_ticks()

    # Update force field duration.
    if state == "playing" and force_field_active:
        if pygame.time.get_ticks() - force_field_start_time > FORCE_FIELD_DURATION:
            force_field_active = False

    if state == "playing":
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            player.angle += player.rotation_speed
        if keys[pygame.K_RIGHT]:
            player.angle -= player.rotation_speed
        if keys[pygame.K_UP]:
            forward = pygame.math.Vector2(1, 0).rotate(-player.angle)
            player.velocity += forward * player.acceleration
            if player.velocity.length() > player.max_speed:
                player.velocity.scale_to_length(player.max_speed)
            player.thrust = True
        else:
            player.thrust = False
        # Faster fire when holding spacebar.
        if keys[pygame.K_SPACE]:
            player.shot_cooldown = 250
            if player.can_shoot():
                bullets.append(player.shoot())
        else:
            player.shot_cooldown = 500
        player.update()

        # Update enemies.
        for enemy in enemies:
            bullet = enemy.update_ai(player)
            enemy.update()
            if bullet:
                enemy_bullets.append(bullet)

        # Update drones.
        for drone in drones:
            bullet = drone.update_ai(enemies)
            drone.update()
            if bullet:
                bullets.append(bullet)

        # Update bullets.
        for bullet in bullets[:]:
            bullet.update()
            if pygame.time.get_ticks() - bullet.spawn_time > bullet.lifetime:
                bullets.remove(bullet)
        for bullet in enemy_bullets[:]:
            bullet.update()
            if pygame.time.get_ticks() - bullet.spawn_time > bullet.lifetime:
                enemy_bullets.remove(bullet)

        # Collisions: Bullets vs. enemies.
        for bullet in bullets[:]:
            for enemy in enemies[:]:
                if math.hypot(bullet.x - enemy.x, bullet.y - enemy.y) < enemy.radius:
                    enemy.health -= 20
                    if bullet in bullets:
                        bullets.remove(bullet)
                    if enemy.health <= 0:
                        explosions.append(Explosion(enemy.x, enemy.y))
                        enemies.remove(enemy)
                        # Count score (and tokens) only if bullet from player.
                        if bullet.owner == "player":
                            score += 100
                            if enemy.color == GREEN:
                                tokens += 1
                    break

        # Collisions: Enemy bullets vs. player (or force field).
        for bullet in enemy_bullets[:]:
            if math.hypot(bullet.x - player.x, bullet.y - player.y) < player.radius:
                if force_field_active:
                    enemy_bullets.remove(bullet)
                else:
                    player.health -= 10
                    enemy_bullets.remove(bullet)
                    if player.health <= 0:
                        state = "game_over"

        # Collisions: Enemy bullets vs. drones.
        for bullet in enemy_bullets[:]:
            for drone in drones[:]:
                if math.hypot(bullet.x - drone.x, bullet.y - drone.y) < drone.radius:
                    drone.health -= 10
                    if bullet in enemy_bullets:
                        enemy_bullets.remove(bullet)
                    if drone.health <= 0:
                        explosions.append(Explosion(drone.x, drone.y))
                        drones.remove(drone)
                    break

        for explosion in explosions[:]:
            explosion.update()
            if explosion.alpha <= 0:
                explosions.remove(explosion)

        # Parallax effect for near stars.
        for i, (sx, sy) in enumerate(stars_near):
            sx -= player.velocity.x * 0.05
            sy -= player.velocity.y * 0.05
            if sx > WIDTH: sx = 0
            elif sx < 0: sx = WIDTH
            if sy > HEIGHT: sy = 0
            elif sy < 0: sy = HEIGHT
            stars_near[i] = (sx, sy)

        # When all enemies are eliminated, advance to next wave.
        if not enemies:
            wave += 1
            enemies = spawn_enemies(wave)

    # ---------------- Rendering -----------------
    screen.fill(BLACK)
    for star in stars_far:
        pygame.draw.circle(screen, WHITE, star, 1)
    for star in stars_near:
        pygame.draw.circle(screen, WHITE, (int(star[0]), int(star[1])), 2)

    if state == "start":
        font_title = pygame.font.SysFont(None, 48)
        title_text = font_title.render("Advanced EVE-Style Space Combat", True, YELLOW)
        screen.blit(title_text, (WIDTH//2 - title_text.get_width()//2, HEIGHT//2 - 180))
        
        font_input = pygame.font.SysFont(None, 36)
        label_text = font_input.render("Enter your name:", True, WHITE)
        screen.blit(label_text, (WIDTH//2 - label_text.get_width()//2, HEIGHT//2 - 110))
        text_box_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 60, 300, 40)
        pygame.draw.rect(screen, WHITE, text_box_rect, 2)
        name_surface = font_input.render(player_name, True, WHITE)
        screen.blit(name_surface, (text_box_rect.x + 5, text_box_rect.y + 5))
        
        mode_display = font_input.render("Press 1 for Standard, 2 for Less Aggressive", True, WHITE)
        screen.blit(mode_display, (WIDTH//2 - mode_display.get_width()//2, HEIGHT//2 - 10))
        current_mode = font_input.render("Current Mode: " + ("Standard" if selected_mode == 1 else "75% Less Aggressive"), True, WHITE)
        screen.blit(current_mode, (WIDTH//2 - current_mode.get_width()//2, HEIGHT//2 + 30))
        
        play_button_rect = pygame.Rect(WIDTH//2 - 75, HEIGHT//2 + 80, 150, 50)
        pygame.draw.rect(screen, GREEN, play_button_rect)
        play_text = font_input.render("Play", True, BLACK)
        screen.blit(play_text, (play_button_rect.x + (play_button_rect.width - play_text.get_width())//2,
                                  play_button_rect.y + (play_button_rect.height - play_text.get_height())//2))
        
        high_scores = get_top_scores()
        font_scores = pygame.font.SysFont(None, 28)
        score_title = font_scores.render("High Scores:", True, GREEN)
        screen.blit(score_title, (WIDTH//2 - score_title.get_width()//2, HEIGHT//2 + 150))
        for idx, (name, score_val) in enumerate(high_scores):
            hs_text = font_scores.render(f"{idx+1}. {name} - {score_val}", True, GREEN)
            screen.blit(hs_text, (WIDTH//2 - hs_text.get_width()//2, HEIGHT//2 + 180 + idx * 30))
            
    elif state == "playing":
        player.draw(screen)
        pygame.draw.rect(screen, RED, (int(player.x - 20), int(player.y - 30), 40, 5))
        pygame.draw.rect(screen, GREEN, (int(player.x - 20), int(player.y - 30), int(40 * (player.health / 100)), 5))
        for enemy in enemies:
            enemy.draw(screen)
            pygame.draw.rect(screen, RED, (int(enemy.x - 20), int(enemy.y - 30), 40, 5))
            pygame.draw.rect(screen, GREEN, (int(enemy.x - 20), int(enemy.y - 30), int(40 * (enemy.health / 100)), 5))
        for drone in drones:
            drone.draw(screen)
            pygame.draw.rect(screen, RED, (int(drone.x - 15), int(drone.y - 25), 30, 4))
            pygame.draw.rect(screen, GREEN, (int(drone.x - 15), int(drone.y - 25), int(30 * (drone.health / 50)), 4))
        for bullet in bullets:
            bullet.draw(screen)
        for bullet in enemy_bullets:
            bullet.draw(screen)
        for explosion in explosions:
            explosion.draw(screen)
        font_hud = pygame.font.SysFont(None, 24)
        score_text = font_hud.render(f"Score: {score}", True, WHITE)
        wave_text = font_hud.render(f"Wave: {wave}", True, WHITE)
        health_text = font_hud.render(f"Player Health: {player.health}", True, WHITE)
        tokens_text = font_hud.render(f"Tokens: {tokens}", True, WHITE)
        screen.blit(score_text, (10, 10))
        screen.blit(wave_text, (10, 30))
        screen.blit(health_text, (10, 50))
        screen.blit(tokens_text, (10, 70))
        if force_field_active:
            pygame.draw.circle(screen, BLUE, (int(player.x), int(player.y)), player.radius + 15, 2)
    elif state == "game_over":
        if not score_saved:
            save_score(player_name, score)
            score_saved = True
        font_over = pygame.font.SysFont(None, 48)
        over_text = font_over.render("GAME OVER", True, RED)
        instr_text = font_over.render("Press R to Restart or Q to Quit", True, RED)
        screen.blit(over_text, (WIDTH//2 - over_text.get_width()//2, HEIGHT//2 - 60))
        screen.blit(instr_text, (WIDTH//2 - instr_text.get_width()//2, HEIGHT//2))
        
    pygame.display.flip()

pygame.quit()
